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
        pack_rss_sync,
        purge_history,
        refresh_forecasts,
        rss_sync,
        scene_auto_grab,
        scene_import,
        wanted_search_sync,
    )

    # Pack RSS sync runs BEFORE magazine RSS sync to avoid duplicates
    # (packs may contain magazines also monitored individually)
    scheduler.add_job(
        pack_rss_sync,
        "interval",
        minutes=30,
        id="pack_rss_sync",
        name="Pack RSS sync",
        replace_existing=True,
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

    # Scene-indexer auto-grab. 6h cadence matches the typical
    # tm.org / Bookys release rhythm — new dailies surface a few
    # times a day, monthlies once a week. Operator can rerun
    # on demand from the magazine detail page in any case.
    scheduler.add_job(
        scene_auto_grab,
        "interval",
        hours=6,
        id="scene_auto_grab",
        name="Scene magazine auto-grab",
        replace_existing=True,
    )

    # Scene importer — short cadence so the status chip flips
    # from "grabbed" to "imported" within a couple of minutes
    # of JD2 finishing the download. Cheap when the JD2 output
    # folder is empty.
    scheduler.add_job(
        scene_import,
        "interval",
        seconds=90,
        id="scene_import",
        name="Scene magazine importer",
        replace_existing=True,
    )

    # Wanted-issue search — pipeline Prowlarr + rules + IA batch +
    # arbiter + auto-grab. Différent du rss_sync (qui ne lit que les
    # feeds) et de scene_auto_grab (qui n'utilise que les scene
    # indexers). L'intervalle est config-driven (défaut 4h) et
    # peut être re-schedulé à chaud via reschedule_wanted_search()
    # sur save des settings.
    from app.dependencies import get_config as _get_config
    try:
        _wsearch_interval = max(1, int(_get_config().wanted_search_interval_minutes))
    except Exception:
        _wsearch_interval = 240
    scheduler.add_job(
        wanted_search_sync,
        "interval",
        minutes=_wsearch_interval,
        id="wanted_search_sync",
        name="Wanted-issue search",
        replace_existing=True,
    )


def reschedule_wanted_search(interval_minutes: int) -> None:
    """Reschedule le job wanted_search_sync en live sans restart backend.

    Appelé par l'endpoint AI settings quand l'user change l'intervalle.
    Clamp à [1, 10080] (1 min à 1 semaine) pour éviter les extrêmes
    (0 min = spam infini, plusieurs semaines = quasi-off silencieux).
    """
    if not scheduler.running:
        logger.debug("scheduler not running — reschedule skipped")
        return
    interval = max(1, min(int(interval_minutes), 10080))
    try:
        scheduler.reschedule_job(
            "wanted_search_sync", trigger="interval", minutes=interval,
        )
        logger.info(
            "wanted_search_sync rescheduled to %d minutes", interval,
        )
    except Exception:
        logger.warning(
            "wanted_search_sync reschedule failed", exc_info=True,
        )

    # Nettoyage périodique des activités « running » orphelines.
    # Sans ça, un import qui se plante silencieusement (backend
    # tué mid-run, worker crashé) reste marqué en cours jusqu'à
    # la prochaine visite de la page /activity — potentiellement
    # des heures. 5 min = compromis raisonnable entre réactivité
    # UI et charge DB.
    async def _cleanup_activities():
        from app.services import activity_service
        try:
            n = await activity_service.cleanup_stale()
            if n:
                logger.info("[activity] auto-failed %d stale runs", n)
        except Exception:  # noqa: BLE001
            logger.warning("Activity cleanup failed (non-fatal)", exc_info=True)

    scheduler.add_job(
        _cleanup_activities,
        "interval",
        minutes=5,
        id="activity_cleanup",
        name="Activity stale cleanup",
        replace_existing=True,
    )

    logger.info("Registered %d scheduled tasks", len(scheduler.get_jobs()))
