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
            from app.parser.magazine_parser import (
                fuzzy_match_title,
                parse_magazine_filename,
            )

            # Get all enabled indexers
            result = await db.execute(
                select(IndexerConfig).where(IndexerConfig.enabled == True)  # noqa: E712
            )
            indexers = result.scalars().all()

            # Get all monitored magazine titles for matching
            mag_result = await db.execute(
                select(Magazine).where(Magazine.monitored == True)  # noqa: E712
            )
            magazines = mag_result.scalars().all()
            known_titles = {m.title: m for m in magazines}

            for indexer in indexers:
                try:
                    client = ProwlarrClient(
                        url=indexer.url, api_key=indexer.api_key
                    )
                    rss_items = await client.rss_feed(categories=[7010, 7020])

                    for item in rss_items:
                        parsed = parse_magazine_filename(item.title)
                        if not parsed.title:
                            continue
                        match = fuzzy_match_title(
                            parsed.title,
                            list(known_titles.keys()),
                            threshold=80.0,
                        )
                        if not match:
                            continue
                        matched_title, _ = match
                        magazine = known_titles[matched_title]

                        # Find matching wanted issue
                        issue_query = select(Issue).where(
                            Issue.magazine_id == magazine.id,
                            Issue.status == "wanted",
                            Issue.monitored == True,  # noqa: E712
                        )
                        if parsed.number is not None:
                            issue_query = issue_query.where(
                                Issue.number == parsed.number
                            )

                        issue_result = await db.execute(issue_query)
                        issue = issue_result.scalars().first()
                        if issue and item.download_url:
                            from app.services.download_service import grab_release

                            await grab_release(
                                db,
                                issue.id,
                                item.download_url,
                                item.title,
                                item.protocol or "torrent",
                                item.guid,
                            )

                except Exception:
                    logger.warning(
                        "RSS sync error for %s",
                        indexer.name,
                        exc_info=True,
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

            delayed = await mark_delayed_forecasts(db)
            if delayed:
                logger.info("Marked %d delayed forecasts", delayed)

            await db.commit()
        except Exception:
            logger.error("Forecast refresh failed", exc_info=True)
