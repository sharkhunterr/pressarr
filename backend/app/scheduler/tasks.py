"""Scheduled background tasks."""
import logging

from app.database import async_session_factory

logger = logging.getLogger(__name__)


async def pack_rss_sync():
    """Search indexers for pack torrents matching learned patterns.

    Runs BEFORE magazine rss_sync to avoid duplicate downloads (packs may
    contain magazines also monitored individually).
    """
    if not async_session_factory:
        return
    async with async_session_factory() as db:
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            from app.indexers.prowlarr import ProwlarrClient
            from app.models.indexer_config import IndexerConfig
            from app.models.pack import Pack
            from app.services.download_service import grab_pack_release
            from app.services.history_service import create_event

            # Get all monitored packs with auto_search enabled
            result = await db.execute(
                select(Pack)
                .options(selectinload(Pack.patterns), selectinload(Pack.rules))
                .where(Pack.monitored == True, Pack.auto_search == True)  # noqa: E712
            )
            packs = list(result.scalars().all())
            if not packs:
                return

            # Get all enabled indexers
            idx_result = await db.execute(
                select(IndexerConfig).where(IndexerConfig.enabled == True)  # noqa: E712
            )
            indexers = idx_result.scalars().all()
            if not indexers:
                return

            total_grabbed = 0

            for pack in packs:
                if not pack.patterns:
                    continue  # No learned patterns yet

                for indexer in indexers:
                    try:
                        from app.services.search_service import get_search_groups, parse_indexer_overrides

                        client = ProwlarrClient(url=indexer.url, api_key=indexer.api_key)
                        global_cats = [int(c) for c in indexer.categories.split(",") if c.strip().isdigit()] or [7000, 7010, 7020]
                        overrides = parse_indexer_overrides(indexer.indexer_overrides)
                        search_groups = get_search_groups(overrides, global_cats)
                        results = []
                        for cats, indexer_ids in search_groups:
                            results.extend(await client.search(pack.search_query, categories=cats, indexer_ids=indexer_ids))

                        for item in results:
                            # Check blocklist
                            from app.services.history_service import is_blocklisted
                            if await is_blocklisted(db, item.title):
                                continue

                            # Fuzzy match against learned patterns
                            from thefuzz import fuzz
                            best_score = 0
                            for pattern in pack.patterns:
                                score = fuzz.ratio(
                                    item.title.lower(), pattern.pattern.lower()
                                )
                                best_score = max(best_score, score)

                            if best_score >= 70 and item.download_url:
                                if pack.auto_grab:
                                    await grab_pack_release(
                                        db,
                                        pack.id,
                                        item.download_url,
                                        item.title,
                                        item.protocol or "torrent",
                                        item.guid,
                                    )
                                    total_grabbed += 1
                                    logger.info(
                                        "Pack RSS: grabbed '%s' for pack '%s' (score=%d)",
                                        item.title, pack.name, best_score,
                                    )
                                    break  # One grab per pack per cycle

                    except Exception:
                        logger.warning(
                            "Pack RSS sync error for pack '%s' on indexer '%s'",
                            pack.name, indexer.name, exc_info=True,
                        )

            if total_grabbed:
                await create_event(
                    db,
                    event_type="searched",
                    details=f"Pack RSS sync: {total_grabbed} packs grabbed",
                    data={
                        "search_type": "pack_rss",
                        "grabbed_count": total_grabbed,
                    },
                )

            await db.commit()
        except Exception:
            logger.error("Pack RSS sync failed", exc_info=True)


async def rss_sync():
    """Query Prowlarr RSS for new releases, auto-grab matching wanted issues."""
    if not async_session_factory:
        return
    async with async_session_factory() as db:
        try:
            from sqlalchemy import select

            from app.indexers.prowlarr import ProwlarrClient
            from app.models.indexer_config import IndexerConfig
            from app.models.issue import Issue
            from app.models.magazine import Magazine
            from app.services.calendar_service import promote_due_forecasts
            from app.services.history_service import create_event
            from app.services.smart_matcher import (
                invalidate_pattern_cache,
                smart_match_rss_item,
            )

            # Step 0: Promote due forecasts before searching
            promoted = await promote_due_forecasts(db)
            if promoted:
                logger.info("Promoted %d due forecasts to wanted", promoted)

            # Get all enabled indexers
            result = await db.execute(
                select(IndexerConfig).where(IndexerConfig.enabled == True)  # noqa: E712
            )
            indexers = result.scalars().all()

            # Get all monitored magazines (with patterns & rules for smart matcher)
            from sqlalchemy.orm import selectinload

            mag_result = await db.execute(
                select(Magazine)
                .where(Magazine.monitored == True)  # noqa: E712
                .options(
                    selectinload(Magazine.patterns),
                    selectinload(Magazine.rules),
                )
            )
            magazines = list(mag_result.scalars().all())

            # Pre-load all wanted issues into lookup dicts (avoid per-item DB queries)
            wanted_result = await db.execute(
                select(Issue).where(
                    Issue.status == "wanted",
                    Issue.monitored == True,  # noqa: E712
                )
            )
            all_wanted = wanted_result.scalars().all()
            wanted_by_number: dict[tuple[int, int], Issue] = {}
            wanted_by_date: dict[tuple[int, int, int], Issue] = {}
            for iss in all_wanted:
                if iss.number is not None:
                    wanted_by_number[(iss.magazine_id, iss.number)] = iss
                if iss.year is not None and iss.month is not None:
                    key = (iss.magazine_id, iss.year, iss.month)
                    if key not in wanted_by_date:
                        wanted_by_date[key] = iss

            rss_total_items = 0
            rss_grabbed = 0
            rss_grabbed_items: list[dict] = []
            rss_indexer_names: list[str] = []
            # Per-indexer fetch failures (Prowlarr unreachable, 4xx/5xx,
            # bad API key…) — surfaced both as their own ``error``
            # history event AND inside the RSS sync's ``data.errors``
            # so the Activity page can show "why nothing was grabbed"
            # at a glance.
            rss_errors: list[dict] = []
            # Items dropped during the per-item loop, broken down by
            # reason. Without this the operator only sees "0 grabbed"
            # and has no way to tell the difference between "RSS feed
            # has nothing I want" and "RSS feed has my issue but the
            # grab failed".
            rss_unmatched = 0
            rss_no_url = 0
            rss_blocklisted = 0
            rss_grab_failed = 0
            # First N un-grabbed titles + reason — enough for the user
            # to sanity-check why their RSS items didn't translate to
            # grabs (capped at 10 to keep the JSON payload small).
            rss_skipped_samples: list[dict] = []

            def _record_skip(title: str, reason: str, **extra) -> None:
                if len(rss_skipped_samples) < 10:
                    rss_skipped_samples.append(
                        {"title": title[:200], "reason": reason, **extra}
                    )

            for indexer in indexers:
                from app.services.search_service import get_search_groups, parse_indexer_overrides

                rss_items: list = []
                try:
                    client = ProwlarrClient(
                        url=indexer.url, api_key=indexer.api_key
                    )
                    global_cats = [int(c) for c in indexer.categories.split(",") if c.strip().isdigit()] or [7000, 7010, 7020]
                    overrides = parse_indexer_overrides(indexer.indexer_overrides)
                    search_groups = get_search_groups(overrides, global_cats)
                    for cats, indexer_ids in search_groups:
                        rss_items.extend(await client.rss_feed(categories=cats, indexer_ids=indexer_ids))
                except Exception as exc:
                    # The fetch itself failed — no items to iterate.
                    # Record a structured error so the operator stops
                    # seeing silent "0 grabbed" RSS runs when the
                    # indexer is actually unreachable.
                    err_msg = f"{type(exc).__name__}: {exc}"
                    logger.warning(
                        "RSS sync error for %s: %s",
                        indexer.name, err_msg, exc_info=True,
                    )
                    rss_errors.append({
                        "indexer": indexer.name,
                        "stage": "fetch",
                        "error": err_msg[:500],
                    })
                    try:
                        await create_event(
                            db,
                            event_type="error",
                            details=f"RSS sync: indexer '{indexer.name}' failed — {err_msg[:200]}",
                            data={
                                "search_type": "rss",
                                "indexer": indexer.name,
                                "stage": "fetch",
                                "error": err_msg[:1000],
                            },
                        )
                    except Exception:
                        logger.debug(
                            "Could not record RSS fetch-error event",
                            exc_info=True,
                        )
                    continue

                rss_total_items += len(rss_items)
                rss_indexer_names.append(indexer.name)

                for item in rss_items:
                    # Wrap every per-item action in its own try/except.
                    # Before this guard, a single failing grab_release
                    # (e.g. download client offline) raised into the
                    # per-indexer except and silently dropped every
                    # remaining item of that indexer.
                    try:
                        match = await smart_match_rss_item(
                            db,
                            item.title,
                            magazines,
                            wanted_by_number=wanted_by_number,
                            wanted_by_date=wanted_by_date,
                        )
                        if not match or not match.issue:
                            rss_unmatched += 1
                            _record_skip(
                                item.title,
                                "no_match",
                                indexer=indexer.name,
                            )
                            continue
                        if not item.download_url:
                            rss_no_url += 1
                            _record_skip(
                                item.title,
                                "no_download_url",
                                indexer=indexer.name,
                                magazine=match.magazine.title,
                            )
                            continue

                        from app.services.history_service import is_blocklisted
                        if await is_blocklisted(db, item.title):
                            rss_blocklisted += 1
                            _record_skip(
                                item.title,
                                "blocklisted",
                                indexer=indexer.name,
                                magazine=match.magazine.title,
                            )
                            logger.debug("RSS: skipping blocklisted '%s'", item.title)
                            continue

                        from app.services.download_service import grab_release

                        await grab_release(
                            db,
                            match.issue.id,
                            item.download_url,
                            item.title,
                            item.protocol or "torrent",
                            item.guid,
                            match_score=match.score,
                            match_details=match.details,
                        )
                        # Auto-learn torrent name as pattern
                        from app.services.magazine_service import (
                            learn_magazine_pattern_from_grab,
                        )

                        await learn_magazine_pattern_from_grab(
                            db, match.magazine.id,
                            item.title, indexer.name,
                        )

                        rss_grabbed += 1
                        rss_grabbed_items.append({
                            "release_title": item.title,
                            "magazine_title": match.magazine.title,
                            "issue_number": match.issue.number,
                            "score": round(match.score, 1),
                            "matched_via": match.matched_via,
                            "indexer": indexer.name,
                        })
                        # Remove from lookup dicts to prevent duplicate grabs
                        if match.issue.number is not None:
                            wanted_by_number.pop(
                                (match.magazine.id, match.issue.number), None
                            )
                        if match.issue.year is not None and match.issue.month is not None:
                            wanted_by_date.pop(
                                (match.magazine.id, match.issue.year, match.issue.month), None
                            )
                        invalidate_pattern_cache(match.magazine.id)

                        logger.info(
                            "RSS: grabbed '%s' for %s #%s (score=%.1f, via=%s, %s)",
                            item.title,
                            match.magazine.title,
                            match.issue.number,
                            match.score,
                            match.matched_via,
                            match.details,
                        )
                    except Exception as exc:
                        # Per-item failure — log + structured event +
                        # keep iterating so the rest of this indexer's
                        # feed still gets a chance.
                        err_msg = f"{type(exc).__name__}: {exc}"
                        rss_grab_failed += 1
                        logger.warning(
                            "RSS sync: grab failed for '%s' on %s: %s",
                            item.title, indexer.name, err_msg,
                            exc_info=True,
                        )
                        rss_errors.append({
                            "indexer": indexer.name,
                            "stage": "grab",
                            "title": item.title[:200],
                            "error": err_msg[:500],
                        })
                        try:
                            await create_event(
                                db,
                                event_type="error",
                                details=f"RSS grab failed: {item.title[:100]} — {err_msg[:200]}",
                                data={
                                    "search_type": "rss",
                                    "indexer": indexer.name,
                                    "stage": "grab",
                                    "release_title": item.title,
                                    "error": err_msg[:1000],
                                },
                            )
                        except Exception:
                            logger.debug(
                                "Could not record RSS grab-error event",
                                exc_info=True,
                            )

            # Record RSS sync history event. Emit even when nothing
            # was scanned IF there were per-indexer fetch errors — the
            # operator needs to see "all indexers failed" rather than
            # silence.
            if rss_total_items > 0 or rss_errors:
                await create_event(
                    db,
                    event_type="searched",
                    details=f"RSS sync: {rss_total_items} items scanned, {rss_grabbed} grabbed",
                    data={
                        "search_type": "rss",
                        "items_scanned": rss_total_items,
                        "grabbed_count": rss_grabbed,
                        "indexers": rss_indexer_names,
                        "grabbed_items": rss_grabbed_items[:20],
                        # Skip-reason breakdown — surfaced in the
                        # Activity > History modal so "0 grabbed" is
                        # explainable instead of mysterious.
                        "unmatched_count": rss_unmatched,
                        "no_url_count": rss_no_url,
                        "blocklisted_count": rss_blocklisted,
                        "grab_failed_count": rss_grab_failed,
                        "skipped_samples": rss_skipped_samples,
                        "errors": rss_errors,
                    },
                )

            await db.commit()
        except Exception:
            logger.error("RSS sync failed", exc_info=True)


async def check_downloads():
    """Poll download clients for completed downloads, trigger import."""
    if not async_session_factory:
        return
    async with async_session_factory() as db:
        try:
            from app.services.download_service import monitor_downloads

            await monitor_downloads(db)
            await db.commit()
        except Exception:
            logger.error("Download check failed", exc_info=True)
            try:
                await db.rollback()
            except Exception:
                pass


async def purge_history():
    """Delete old history entries."""
    if not async_session_factory:
        return
    async with async_session_factory() as db:
        try:
            from app.services.history_service import purge_old_events

            count = await purge_old_events(db)
            if count:
                logger.info("Purged %d old history entries", count)
            await db.commit()
        except Exception:
            logger.error("History purge failed", exc_info=True)


async def cleanup_orphaned_snatched():
    """Reset issues stuck in 'snatched' with no active download."""
    if not async_session_factory:
        return
    async with async_session_factory() as db:
        try:
            from app.services.download_service import (
                cleanup_orphaned_snatched as do_cleanup,
            )

            count = await do_cleanup(db)
            if count:
                logger.info("Reset %d orphaned snatched issues to wanted", count)
            await db.commit()
        except Exception:
            logger.error("Orphaned snatched cleanup failed", exc_info=True)


async def refresh_forecasts():
    """Recalculate forecasts for all monitored magazines."""
    if not async_session_factory:
        return
    async with async_session_factory() as db:
        try:
            from sqlalchemy import select

            from app.models.magazine import Magazine
            from app.services.calendar_service import (
                generate_forecasts,
                mark_delayed_forecasts,
            )

            result = await db.execute(
                select(Magazine).where(Magazine.monitored == True)  # noqa: E712
            )
            magazines = result.scalars().all()

            for magazine in magazines:
                await generate_forecasts(db, magazine)

            # Promote due forecasts before marking delayed ones
            from app.services.calendar_service import promote_due_forecasts

            promoted = await promote_due_forecasts(db)
            if promoted:
                logger.info("Promoted %d due forecasts to wanted", promoted)

            delayed = await mark_delayed_forecasts(db)
            if delayed:
                logger.info("Marked %d delayed forecasts", delayed)

            await db.commit()
        except Exception:
            logger.error("Forecast refresh failed", exc_info=True)



async def scene_auto_grab():
    """Auto-grab cycle for the scene magazine indexers (Bookys,
    telecharger-magazines.org, …).

    For each monitored magazine, scans every enabled indexer
    and dispatches matching releases to the JDownloader 2
    folder-watch. Subscription requests grab everything new on
    or after ``monitoring_start_date``; one-shot requests grab
    only the matching back-issue and then flip ``monitored=False``.

    Safe to run on a cadence (default: every 6 hours via
    ``app.scheduler``); the orchestrator dedupes on
    ``(source, source_url)`` so re-scans don't double-dispatch.
    """
    if not async_session_factory:
        return
    async with async_session_factory() as db:
        try:
            from app.dependencies import get_config
            from app.services.auto_grab_service import run_auto_grab

            stats = await run_auto_grab(db, get_config())
            if stats["scanned"]:
                logger.info(
                    "Scene auto-grab: scanned=%d grabbed=%d skipped=%d",
                    stats["scanned"], stats["grabbed"], stats["skipped"],
                )
        except Exception:
            logger.error("Scene auto-grab cycle failed", exc_info=True)


async def scene_import():
    """Walk JDownloader 2's output directory and move completed
    files into the magazine library, flipping the matching
    ``MagazineRelease`` row from ``grabbed`` to ``imported``.

    Cadence is short (every 90s) because most magazines are
    PDF and finish in a minute or two — operator feedback is
    way better when the status chip flips quickly.
    """
    if not async_session_factory:
        return
    async with async_session_factory() as db:
        try:
            from app.dependencies import get_config
            from app.services.scene_importer import run_scene_import

            stats = await run_scene_import(db, get_config())
            if stats["imported"]:
                logger.info(
                    "Scene importer: imported=%d scanned=%d skipped=%d",
                    stats["imported"], stats["scanned"], stats["skipped"],
                )
        except Exception:
            logger.error("Scene importer cycle failed", exc_info=True)
