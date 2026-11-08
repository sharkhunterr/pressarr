"""Follow scene grabs through JDownloader, the way torrents are followed.

The ``.crawljob`` the dispatcher writes tags its link with the comment
``pressarr:release=<id>``; JD2's local API (``jdownloader_api.py``)
tells where each tagged link stands. Every cycle, for each grabbed
release:

- no link yet: the crawljob waits in the folder-watch directory;
- in the LinkGrabber: JD2 is checking the link — OFFLINE means that
  mirror is gone;
- in the download list: its progress goes to a ``download`` activity,
  like a torrent's; a skipped link or a failure status (captcha,
  offline, plugin defect) means that mirror failed;
- finished: the file goes through the torrent import (parser, AI
  analysis), then the link leaves JD2's list.

A failed mirror leaves JD2 and the next one is dispatched; once none is
left, the release fails with the reason.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.magazine import Magazine
from app.models.magazine_release import MagazineRelease
from app.services import activity_service
from app.services.jdownloader_api import JDownloaderApi, JDownloaderApiError
from app.services.jdownloader_dispatcher import (
    JDownloaderDispatchError,
    JDownloaderSetupError,
    dispatch_release,
    tried_hosters,
)

logger = logging.getLogger(__name__)

_TAG = re.compile(r"pressarr:release=(\d+)")
# JD2 takes a crawljob within seconds; a link that has still not shown
# up this long after its dispatch never will: JD2 has no plugin for
# that hoster and drops it without a word.
_UNSUPPORTED_AFTER = timedelta(minutes=2)
# A mirror that has sent nothing this long after its dispatch is stuck:
# JD2 loops on a free hoster's captcha it cannot solve ("Wait 52s",
# "Starting...", again). Long enough for 1fichier's free wait.
_STALLED_AFTER = timedelta(minutes=10)

# Releases whose file is being imported; the import outlives a cycle.
_importing: set[int] = set()
# Release → hoster of the link last seen in JD2: once seen, a link
# that goes missing was removed there, not dropped.
_seen: dict[int, str] = {}
_background: set[asyncio.Task] = set()


def _release_id(link: dict) -> int | None:
    m = _TAG.search(link.get("comment") or "")
    return int(m.group(1)) if m else None


def _failure(link: dict) -> str | None:
    """Why JD2 gave up on a download-list link, or None while it is
    still on it. A stopped link shows why it stopped ("File not
    found", "Skipped - Captcha", "Try restarting this link (plugin
    outdated?)"); a queued one shows nothing, a waiting one "Wait …"."""
    if link.get("finished") or link.get("running"):
        return None
    status = link.get("status") or ""
    if link.get("skipped") or (status and not status.lower().startswith("wait")):
        return status or "skipped"
    return None


def _local_path(save_to: str, name: str, config) -> Path:
    """The file JD2 wrote, as pressarr sees it."""
    jd_root = (config.jdownloader_output_path_in_jd2 or "").rstrip("/")
    local_root = (config.jdownloader_output_path or "").rstrip("/")
    if jd_root and (save_to == jd_root or save_to.startswith(jd_root + "/")):
        save_to = local_root + save_to[len(jd_root):]
    return Path(save_to) / name


async def track_scene_downloads(db: AsyncSession, config) -> None:
    """One pass over the grabbed releases."""
    api_url = getattr(config, "jdownloader_api_url", "")
    if not (getattr(config, "jdownloader_enabled", False) and api_url):
        return
    releases = (
        await db.scalars(
            select(MagazineRelease).where(MagazineRelease.status == "grabbed")
        )
    ).all()
    if not releases:
        return

    api = JDownloaderApi(api_url)
    try:
        try:
            grabber = await api.linkgrabber_links()
            downloads = await api.download_links()
            packages = {
                p["uuid"]: p.get("saveTo") or "" for p in await api.download_packages()
            }
        except JDownloaderApiError as e:
            logger.warning("Scene downloads not followed: %s", e)
            return
        links: dict[int, list[tuple[str, dict]]] = {}
        for where, rows in (("grabber", grabber), ("downloads", downloads)):
            for link in rows:
                rid = _release_id(link)
                if rid is not None:
                    links.setdefault(rid, []).append((where, link))

        for release in releases:
            if release.id in _importing:
                continue
            try:
                await _follow(db, api, config, release, links.get(release.id, []), packages)
            except Exception:
                logger.exception("Scene download of release id=%s: not followed", release.id)
        await db.commit()
    finally:
        await api.close()


async def _follow(
    db: AsyncSession,
    api: JDownloaderApi,
    config,
    release: MagazineRelease,
    links: list[tuple[str, dict]],
    packages: dict[int, str],
) -> None:
    # A restart cancels the running activities: pick this one up again,
    # with the mirrors already tried, rather than open a new one.
    previous = await activity_service.find_by_external_id(
        "download", f"jd:{release.id}", live_only=False
    )
    if previous is not None and (await activity_service.get(previous)).status == "cancelled":
        await activity_service.reopen(previous)
    aid = await activity_service.create(
        kind="download",
        title=release.title,
        subtitle="JDownloader",
        magazine_id=release.magazine_id,
        external_id=f"jd:{release.id}",
        payload={
            "release_id": release.id,
            "protocol": "scene",
            "download_client": "JDownloader",
            "size": release.size_bytes,
        },
    )
    hoster = (tried_hosters(release) or ["?"])[-1]

    if not links:
        if _seen.get(release.id) == hoster:
            _seen.pop(release.id)
            await _fail(db, release, aid, "JDownloader n'a plus ce lien")
            return
        pending = any(
            Path(config.jdownloader_folderwatch or "").glob(f"*-{release.id}.crawljob")
        )
        recent = (
            release.grabbed_at is not None
            and datetime.utcnow() - release.grabbed_at < _UNSUPPORTED_AFTER
        )
        if pending or recent:
            await activity_service.update_progress(
                aid, 0, status_message=f"{hoster} — en attente de JDownloader"
            )
        else:
            await _next_mirror(
                db, config, release, aid, hoster,
                f"{hoster} : lien non pris en charge par JDownloader",
            )
        return

    # The latest link, should an older one linger.
    where, link = max(links, key=lambda wl: wl[1].get("uuid") or 0)
    host = link.get("host") or hoster
    _seen[release.id] = host

    if where == "grabber":
        if link.get("availability") == "OFFLINE":
            await api.remove_linkgrabber_links([link["uuid"]])
            await _next_mirror(db, config, release, aid, host, f"{host} : fichier hors ligne")
        else:
            await activity_service.update_progress(
                aid, 0, status_message=f"{host} — vérification du lien"
            )
        return

    if link.get("finished"):
        path = _local_path(packages.get(link.get("packageUUID"), ""), link.get("name") or "", config)
        await activity_service.mark_done(aid, hint=f"{path.name} — import")
        _importing.add(release.id)
        task = asyncio.get_running_loop().create_task(
            _import(release.id, path, link["uuid"], config)
        )
        _background.add(task)
        task.add_done_callback(_background.discard)
        return

    failure = _failure(link)
    loaded = link.get("bytesLoaded") or 0
    if (
        not failure
        and loaded == 0
        and release.grabbed_at is not None
        and datetime.utcnow() - release.grabbed_at > _STALLED_AFTER
    ):
        failure = f"rien reçu en {_STALLED_AFTER.seconds // 60} min (captcha ?)"
    if failure:
        await api.remove_download_links([link["uuid"]])
        await _next_mirror(db, config, release, aid, host, f"{host} : {failure}")
        return

    total = link.get("bytesTotal") or 0
    if total <= 0:
        total = release.size_bytes or 0
    eta = link.get("eta") or 0
    message = f"{host} — {link.get('status') or 'téléchargement'}"
    if link.get("speed"):
        message += f" — {int(link['speed'] / 1024)} KB/s"
        if 0 < eta < 86400:
            message += f" · ETA {eta // 60}m{eta % 60:02d}s"
    await activity_service.update_progress(
        aid, min(99.0, 100 * loaded / total) if total > 0 else 0, status_message=message
    )


async def _next_mirror(
    db: AsyncSession,
    config,
    release: MagazineRelease,
    aid: int,
    failed_host: str,
    reason: str,
) -> None:
    # Grabs dispatched before the hosters were recorded name none.
    tried = tried_hosters(release)
    if failed_host not in tried:
        release.tried_hosters = json.dumps([*tried, failed_host])
    magazine = await db.get(Magazine, release.magazine_id)
    try:
        dispatch_release(release=release, magazine=magazine, config=config, next_mirror=True)
    except JDownloaderSetupError as e:
        # JDownloader's setup is at fault: the release stays grabbable.
        release.status = "available"
        release.status_message = None
        await activity_service.mark_error(aid, f"{reason} — {e}")
        return
    except JDownloaderDispatchError:
        await _fail(db, release, aid, f"{reason} — aucun autre miroir")
        return
    logger.info("Scene download of release id=%s: %s, next mirror", release.id, reason)
    await activity_service.push_step(
        aid,
        {"step": "mirror", "label": reason},
        status_message=f"{reason} — essai de {tried_hosters(release)[-1]}",
    )


async def _fail(
    db: AsyncSession, release: MagazineRelease, aid: int, reason: str
) -> None:
    from app.services.history_service import create_event

    _seen.pop(release.id, None)
    release.status = "failed"
    release.status_message = reason[:500]
    await activity_service.mark_error(aid, reason)
    await create_event(
        db,
        event_type="error",
        magazine_id=release.magazine_id,
        details=f"Scene download failed: {release.title} — {reason}",
        data={"release_id": release.id, "source": release.source, "reason": reason},
    )


async def _import(release_id: int, path: Path, link_id: int, config) -> None:
    """Import the downloaded file like a torrent's, in its own session:
    the AI analysis takes minutes."""
    from app.database import async_session_factory
    from app.services.import_service import process_downloaded_file

    try:
        async with async_session_factory() as db:
            release = await db.get(MagazineRelease, release_id)
            if release is None:
                return
            try:
                result = await process_downloaded_file(
                    db,
                    path,
                    config,
                    magazine_id=release.magazine_id,
                    source_type="scene",
                    source_release_title=release.title,
                )
            except Exception as e:
                # Not retried every cycle: the file would fail the same way.
                logger.exception("Scene import of release id=%s failed", release_id)
                await db.rollback()
                result = {"success": False, "message": str(e)}
            if result.get("success"):
                release.status = "imported"
                release.status_message = (result.get("message") or "Imported")[:500]
                api = JDownloaderApi(config.jdownloader_api_url)
                try:
                    await api.remove_download_links([link_id])
                except JDownloaderApiError:
                    logger.debug("JD2 link %s left in place", link_id)
                finally:
                    await api.close()
            else:
                release.status = "failed"
                release.status_message = f"Import: {result.get('message')}"[:500]
            await db.commit()
    finally:
        _importing.discard(release_id)
