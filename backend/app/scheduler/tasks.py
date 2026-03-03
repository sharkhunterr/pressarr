"""Scheduled background tasks."""
import logging

from app.database import async_session_factory

logger = logging.getLogger(__name__)


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

            for indexer in indexers:
                try:
                    client = ProwlarrClient(
                        url=indexer.url, api_key=indexer.api_key
                    )
                    rss_items = await client.rss_feed(categories=[7010, 7020])
                    rss_total_items += len(rss_items)

                    for item in rss_items:
                        match = await smart_match_rss_item(
                            db,
                            item.title,
                            magazines,
                            wanted_by_number=wanted_by_number,
                            wanted_by_date=wanted_by_date,
                        )
                        if match and match.issue and item.download_url:
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
