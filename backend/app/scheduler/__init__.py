"""APScheduler setup for background tasks."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the scheduler if not already running."""
    if not scheduler.running:
        _register_tasks()
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def _register_tasks() -> None:
    """Register all periodic background tasks."""
    from app.scheduler.tasks import (
        check_downloads,
        cleanup_orphaned_snatched,
        purge_history,
        refresh_forecasts,
        rss_sync,
    )

    scheduler.add_job(
        rss_sync,
        "interval",
        minutes=30,
        id="rss_sync",
        name="RSS sync",
        replace_existing=True,
    )

    scheduler.add_job(
        check_downloads,
        "interval",
        seconds=30,
        id="check_downloads",
        name="Download check",
        replace_existing=True,
    )

    scheduler.add_job(
        purge_history,
        "interval",
        hours=24,
        id="purge_history",
        name="History purge",
        replace_existing=True,
    )

    scheduler.add_job(
        refresh_forecasts,
        "interval",
        hours=24,
        id="refresh_forecasts",
        name="Forecast refresh",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_orphaned_snatched,
        "interval",
        hours=6,
        id="cleanup_orphaned_snatched",
        name="Orphaned snatched cleanup",
        replace_existing=True,
    )

    logger.info("Registered %d scheduled tasks", len(scheduler.get_jobs()))
