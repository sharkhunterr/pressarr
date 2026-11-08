"""Auto-grab orchestrator.

For each monitored magazine, periodically:

1. Scan every enabled scene indexer (Bookys, tm.org, …).
2. Pick the best release(s) matching the magazine's request
   shape:
     - ``subscription`` → grab all available releases whose
       published date is on/after the ``monitoring_start_date``
       and that haven't been grabbed yet.
     - ``one_shot`` → grab the single release matching
       ``target_issue_label`` or ``target_issue_date``, then
       optionally flip the magazine to ``monitored=False`` so
       the same back-issue isn't re-fetched on the next tick.
3. Dispatch the picks through the JD2 folder-watch helper.

Failure modes are isolated per magazine — one stuck scrape
doesn't poison the rest of the loop. Skips entirely when no
indexer / no download client is enabled.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.magazine import Magazine
from app.models.magazine_release import MagazineRelease
from app.services.jdownloader_dispatcher import (
    JDownloaderDispatchError,
    JDownloaderSetupError,
    dispatch_release,
)
from app.services.magazine_release_service import scan_magazine_releases

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Target-matching for one-shot requests
# ----------------------------------------------------------------------


def _normalise_issue_label(raw: str | None) -> str:
    """Strip every non-alphanumeric so "N°594" and "N 594" and
    "#594" all collapse to "n594". Comparison key only — never
    surfaced to the operator."""
    if not raw:
        return ""
    return re.sub(r"[^a-zA-Z0-9]+", "", raw).lower()


def _release_matches_one_shot(
    release: MagazineRelease, magazine: Magazine
) -> bool:
    """``one_shot`` magazine accepts a release iff it matches
    the operator's ``target_issue_label`` OR
    ``target_issue_date`` (either one — operator picks the
    convention the magazine uses)."""
    if magazine.target_issue_label:
        if _normalise_issue_label(
            release.issue_label
        ) == _normalise_issue_label(magazine.target_issue_label):
            return True
        # Fall back to substring match on the full title so
        # operator-typed "594" matches "Picsou Magazine N°594".
        if _normalise_issue_label(magazine.target_issue_label) in (
            _normalise_issue_label(release.title)
        ):
            return True
    if magazine.target_issue_date:
        wanted = magazine.target_issue_date.isoformat()
        if release.published_at and wanted in release.published_at:
            return True
        # Day/month/year combination also routinely appears in
        # the title for dailies — "L'Equipe du 03 Juin 2026".
        d = magazine.target_issue_date
        title_lc = (release.title or "").lower()
        # Cheap day-then-month match: "3 juin", "03 juin", "03/06"
        month_fr = [
            "", "janvier", "fevrier", "mars", "avril", "mai", "juin",
            "juillet", "aout", "septembre", "octobre", "novembre",
            "decembre",
        ]
        if (
            f"{d.day:02d}/{d.month:02d}/{d.year}" in title_lc
            or f"{d.day} {month_fr[d.month]} {d.year}" in title_lc
            or f"{d.day:02d} {month_fr[d.month]} {d.year}" in title_lc
        ):
            return True
    return False


# ----------------------------------------------------------------------
# Subscription filtering
# ----------------------------------------------------------------------


def _release_after_watch_date(
    release: MagazineRelease, watch_from: date | None
) -> bool:
    """Subscription mode keeps every release published on/after
    the operator's ``monitoring_start_date``. Releases with no
    publish date are kept too — better to grab one stale
    issue than to silently drop a freshly-scraped one because
    the indexer didn't ship a date."""
    if watch_from is None:
        return True
    if not release.published_at:
        return True
    # ``published_at`` is best-effort ISO from the scraper;
    # accept the leading 10 chars (date) when the full timestamp
    # isn't there.
    head = release.published_at[:10]
    try:
        parsed = date.fromisoformat(head)
    except ValueError:
        return True
    return parsed >= watch_from


# ----------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------


async def run_auto_grab(db: AsyncSession, config) -> dict[str, int]:
    """Run one auto-grab cycle across every monitored magazine.
    Returns a small stats dict (``{ "scanned": …, "grabbed":
    …, "skipped": … }``) so the scheduler log lines stay
    informative.

    Enregistre une activité ``kind=scan`` dans la table Activity
    pour que la page /activité + le badge sidebar reflètent le
    cycle en cours. L'activité est marquée done avec les stats
    en hint à la fin du cycle.
    """
    from app.services import activity_service

    if not getattr(config, "jdownloader_enabled", False):
        logger.debug(
            "Auto-grab skipped: JDownloader dispatcher disabled in config"
        )
        return {"scanned": 0, "grabbed": 0, "skipped": 0}

    magazines = (
        await db.scalars(
            select(Magazine).where(Magazine.monitored.is_(True))
        )
    ).all()

    if not magazines:
        return {"scanned": 0, "grabbed": 0, "skipped": 0}

    stats = {"scanned": 0, "grabbed": 0, "skipped": 0}

    # Une activité par cycle. Retourne un id qu'on mettra à jour au
    # fil du scan (progress + push_step par magazine touché).
    activity_id: int | None = None
    try:
        activity_id = await activity_service.create(
            kind="scan",
            title=f"Auto-grab · {len(magazines)} magazines monitorés",
            subtitle="Recherche indexeurs + dispatch JDownloader",
            payload={"magazine_count": len(magazines)},
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Activity mirror (scan register) failed: %s", exc)

    for mag in magazines:
        stats["scanned"] += 1
        try:
            grabbed = await _process_magazine(mag, db, config)
            stats["grabbed"] += grabbed
            if activity_id is not None:
                try:
                    await activity_service.push_step(
                        activity_id,
                        {
                            "step": "scan_magazine",
                            "label": f"Scan {mag.title}",
                            "hint": (
                                f"{grabbed} grab(s)" if grabbed
                                else "aucun release grabbable"
                            ),
                            "magazine_id": mag.id,
                        },
                    )
                    await activity_service.update_progress(
                        activity_id,
                        stats["scanned"] * 100 / len(magazines),
                    )
                except Exception:  # noqa: BLE001
                    pass
        except Exception:
            logger.exception(
                "Auto-grab cycle failed for magazine id=%s title=%r",
                mag.id, mag.title,
            )
            stats["skipped"] += 1
            if activity_id is not None:
                try:
                    await activity_service.push_step(
                        activity_id,
                        {
                            "step": "scan_error",
                            "label": f"Erreur sur {mag.title}",
                            "hint": "voir logs",
                            "magazine_id": mag.id,
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass

    if stats["scanned"]:
        logger.info(
            "Auto-grab cycle complete: scanned=%(scanned)d "
            "grabbed=%(grabbed)d skipped=%(skipped)d",
            stats,
        )
    if activity_id is not None:
        try:
            await activity_service.mark_done(
                activity_id,
                hint=(
                    f"{stats['scanned']} scannés · "
                    f"{stats['grabbed']} grabs · "
                    f"{stats['skipped']} erreurs"
                ),
            )
        except Exception:  # noqa: BLE001
            pass
    return stats


async def _process_magazine(
    magazine: Magazine,
    db: AsyncSession,
    config,
) -> int:
    """Scan + pick + dispatch for a single magazine. Returns
    the number of releases grabbed in this cycle (0 most of
    the time once the back-catalogue is drained)."""

    if not getattr(config, "jdownloader_enabled", False):
        return 0
    releases = await scan_magazine_releases(magazine, config, db)
    if not releases:
        return 0

    # Already-grabbed rows never get re-dispatched; we read
    # them out of the DB so a previous cycle's grab survives
    # a process restart.
    available = [r for r in releases if r.status == "available"]
    if not available:
        return 0

    is_one_shot = magazine.request_type == "one_shot"
    picks: list[MagazineRelease]
    if is_one_shot:
        # Pick at most one matching release; if more than one
        # matches (rare but possible — operator gave a numeric
        # label that collides with an HS), grab the newest by
        # discovery time. The other matches stay available so
        # the operator can fix the target.
        candidates = [
            r for r in available if _release_matches_one_shot(r, magazine)
        ]
        if not candidates:
            logger.debug(
                "Auto-grab: no release matches one-shot target for "
                "magazine id=%s (target_label=%r target_date=%r)",
                magazine.id, magazine.target_issue_label,
                magazine.target_issue_date,
            )
            return 0
        candidates.sort(
            key=lambda r: r.discovered_at or datetime.min, reverse=True
        )
        picks = [candidates[0]]
        # --- AI ranker (optional) : re-consulte les candidats avant
        # le pick final. Le scorer natif reste maître par défaut
        # (mode ai_advisory) — l'IA log son avis mais ne change rien
        # tant que l'user n'a pas basculé en ai_wins / ai_veto_only.
        if getattr(config, "ai_ranker_enabled", False) and len(candidates) > 1:
            picks = await _apply_ai_ranker(
                candidates=candidates,
                magazine=magazine,
                config=config,
                default_pick=picks[0],
            )
    else:
        # Subscription: take everything after the watch-date.
        picks = [
            r
            for r in available
            if _release_after_watch_date(r, magazine.monitoring_start_date)
        ]

    from app.services.history_service import create_event

    grabbed = 0
    for release in picks:
        try:
            crawljob_path = dispatch_release(
                release=release, magazine=magazine, config=config
            )
            grabbed += 1
            try:
                await create_event(
                    db,
                    event_type="grab",
                    magazine_id=magazine.id,
                    details=f"Grabbed (scene auto): {release.title}",
                    data={
                        "release_id": release.id,
                        "release_title": release.title,
                        "source": release.source,
                        "source_url": release.source_url,
                        "crawljob": crawljob_path.name,
                        "auto": True,
                    },
                )
            except Exception:
                logger.debug(
                    "Auto-grab: history event write failed", exc_info=True
                )
        except JDownloaderSetupError as e:
            # Every other pick would fail the same way; they stay
            # available for the next cycle.
            logger.warning(
                "Auto-grab stopped for magazine id=%s: %s", magazine.id, e
            )
            break
        except JDownloaderDispatchError as e:
            release.status = "failed"
            release.status_message = str(e)
            logger.warning(
                "Auto-grab dispatch failed for release id=%s: %s",
                release.id, e,
            )
            try:
                await create_event(
                    db,
                    event_type="error",
                    magazine_id=magazine.id,
                    details=f"Scene grab failed: {e!s}",
                    data={
                        "release_id": release.id,
                        "release_title": release.title,
                        "source": release.source,
                        "reason": str(e),
                        "auto": True,
                    },
                )
            except Exception:
                logger.debug(
                    "Auto-grab: history error event write failed",
                    exc_info=True,
                )

    if grabbed:
        await db.commit()
        # When one-shot, flip ``monitored`` off so the next cycle
        # doesn't keep scanning a magazine the operator is done
        # with. Subscription mode stays monitored forever.
        if is_one_shot:
            magazine.monitored = False
            await db.commit()

    return grabbed


def hoster_count_for(release: MagazineRelease) -> int:
    """Helper for logs / tests — extracted so callers can ask
    "did this release end up with any usable hoster URLs?"
    without re-parsing the JSON column."""
    try:
        return len(json.loads(release.hoster_links or "[]"))
    except Exception:
        return 0


async def _apply_ai_ranker(
    candidates: list[MagazineRelease],
    magazine,
    config,
    default_pick: MagazineRelease,
) -> list[MagazineRelease]:
    """Consult the AI ranker over the candidate list.

    Returns a picks list (0 or 1 items). Empty list means the AI
    vetoed the top candidate in ``ai_veto_only`` mode — the caller
    then skips the grab entirely, which is the whole point of the
    veto mode.

    Any failure inside the ranker (Ollama down, timeout, parse error)
    is caught here and we return ``[default_pick]`` unchanged — the
    ranker is optional and must never block the grab flow.
    """
    try:
        from app.database import async_session_factory
        from app.services.ai_ranker_service import (
            AIRankerService,
            RankerCandidate,
        )

        rc = [
            RankerCandidate(
                id=str(r.id),
                title=r.title or "",
                publish_date=(
                    r.discovered_at.isoformat() if r.discovered_at else None
                ),
            )
            for r in candidates
        ]
        svc = AIRankerService(config, async_session_factory)
        result = await svc.rank(
            candidates=rc,
            magazine_id=magazine.id,
            pattern_id=None,  # magazine-level ranker, not pattern
            magazine_title_hint=magazine.title,
            issue_hint=magazine.target_issue_label,
        )
        logger.info(
            "AI ranker run=%s mode=%s scorer_top=%s ai_pick=%s "
            "conf=%s vetoed=%s reason=%s",
            result.run_id, result.applied_mode,
            result.scorer_top_index, result.final_pick_index,
            result.confidence, result.vetoed_top, result.reason,
        )
        if result.vetoed_top:
            logger.info(
                "AI ranker vetoed top pick for magazine id=%s — skip grab",
                magazine.id,
            )
            return []
        if result.final_pick_index is None:
            return [default_pick]
        return [candidates[result.final_pick_index]]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "AI ranker failed (non-fatal, keeping default pick): %s",
            exc,
            exc_info=True,
        )
        return [default_pick]


# Scans started for newly added magazines; referenced until done.
_background: set[asyncio.Task] = set()


def grab_after_commit(db: AsyncSession, magazine_id: int) -> None:
    """Scan and dispatch ``magazine_id`` in the background once
    ``db`` commits it, so a newly added title fetches its
    back-catalogue without waiting for the next cycle. A Bookys
    scrape takes a minute: whoever adds the magazine does not wait
    for it."""
    from app.database import async_session_factory
    from app.dependencies import get_config

    if async_session_factory is None or not getattr(
        get_config(), "jdownloader_enabled", False
    ):
        return

    async def run() -> None:
        try:
            async with async_session_factory() as bg:
                magazine = await bg.get(Magazine, magazine_id)
                if magazine is not None and magazine.monitored:
                    await _process_magazine(magazine, bg, get_config())
                    await bg.commit()
        except Exception:
            logger.warning(
                "Scene auto-grab of new magazine id=%s failed",
                magazine_id,
                exc_info=True,
            )

    def start(_session) -> None:
        task = asyncio.get_running_loop().create_task(run())
        _background.add(task)
        task.add_done_callback(_background.discard)

    event.listen(db.sync_session, "after_commit", start, once=True)

