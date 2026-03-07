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
                        client = ProwlarrClient(url=indexer.url, api_key=indexer.api_key)
                        results = await client.search(pack.search_query, categories=[7010, 7020])

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

            # Get all monitored magazines
            mag_result = await db.execute(
                select(Magazine).where(Magazine.monitored == True)  # noqa: E712
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

            for indexer in indexers:
                try:
                    client = ProwlarrClient(
                        url=indexer.url, api_key=indexer.api_key
                    )
                    rss_items = await client.rss_feed(categories=[7010, 7020])
                    rss_total_items += len(rss_items)
                    rss_indexer_names.append(indexer.name)

                    for item in rss_items:
                        match = await smart_match_rss_item(
                            db,
                            item.title,
                            magazines,
                            wanted_by_number=wanted_by_number,
                            wanted_by_date=wanted_by_date,
                        )
                        if match and match.issue and item.download_url:
                            # Check blocklist before grabbing
                            from app.services.history_service import is_blocklisted
                            if await is_blocklisted(db, item.title):
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

                except Exception:
                    logger.warning(
                        "RSS sync error for %s",
                        indexer.name,
                        exc_info=True,
                    )

            # Record RSS sync history event
            if rss_total_items > 0:
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
