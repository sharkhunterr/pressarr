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

import json
import logging
import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.magazine import Magazine
from app.models.magazine_release import MagazineRelease
from app.services.jdownloader_dispatcher import (
    JDownloaderDispatchError,
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
    informative."""

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

    stats = {"scanned": 0, "grabbed": 0, "skipped": 0}

    for mag in magazines:
        stats["scanned"] += 1
        try:
            grabbed = await _process_magazine(mag, db, config)
            stats["grabbed"] += grabbed
        except Exception:
            logger.exception(
                "Auto-grab cycle failed for magazine id=%s title=%r",
                mag.id, mag.title,
            )
            stats["skipped"] += 1

    if stats["scanned"]:
        logger.info(
            "Auto-grab cycle complete: scanned=%(scanned)d "
            "grabbed=%(grabbed)d skipped=%(skipped)d",
            stats,
        )
    return stats


async def _process_magazine(
    magazine: Magazine,
    db: AsyncSession,
    config,
) -> int:
    """Scan + pick + dispatch for a single magazine. Returns
    the number of releases grabbed in this cycle (0 most of
    the time once the back-catalogue is drained)."""

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
