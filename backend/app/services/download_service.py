"""Download management service."""
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.download_client import DownloadClient
from app.models.issue import Issue
from app.schemas.search import GrabResponse
from app.services.history_service import create_event

logger = logging.getLogger(__name__)

# Persistent file for grab registry (survives container restarts)
_GRAB_REGISTRY_PATH: Path | None = None


@dataclass
class _GrabInfo:
    """Tracks which issue or pack a download belongs to."""
    issue_id: int
    magazine_id: int
    pack_id: int | None = None


# download_id → GrabInfo — populated at grab time, consumed at import time
_grab_registry: dict[str, _GrabInfo] = {}

# download_ids that have already been imported (prevents re-processing)
_processed_downloads: set[str] = set()

# Track whether the registry has been loaded from disk
_registry_loaded: bool = False

# Track consecutive import failures per download_id (avoids warning spam)
_import_fail_count: dict[str, int] = {}

# Maximum consecutive import failures before giving up on a download
MAX_IMPORT_FAILURES = 10


def _get_registry_path() -> Path:
    """Get the path for the persistent grab registry file."""
    global _GRAB_REGISTRY_PATH
    if _GRAB_REGISTRY_PATH is None:
        from app.dependencies import get_config
        config = get_config()
        _GRAB_REGISTRY_PATH = config.config_path.parent / "grab_registry.json"
    return _GRAB_REGISTRY_PATH


def _get_processed_path() -> Path:
    """Get the path for the persistent processed-downloads file."""
    return _get_registry_path().with_name("processed_downloads.json")


def _get_fail_count_path() -> Path:
    """Get the path for the persistent import fail count file."""
    return _get_registry_path().with_name("import_fail_counts.json")


def _save_registry() -> None:
    """Persist grab registry and processed set to disk."""
    try:
        path = _get_registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: asdict(v) for k, v in _grab_registry.items()}
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        logger.warning("Could not save grab registry", exc_info=True)
    try:
        proc_path = _get_processed_path()
        proc_path.parent.mkdir(parents=True, exist_ok=True)
        proc_path.write_text(json.dumps(list(_processed_downloads)))
    except Exception:
        logger.warning("Could not save processed downloads", exc_info=True)
    try:
        fail_path = _get_fail_count_path()
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps(_import_fail_count))
    except Exception:
        logger.warning("Could not save import fail counts", exc_info=True)


def _load_registry() -> None:
    """Load grab registry and processed set from disk on startup."""
    global _registry_loaded
    try:
        path = _get_registry_path()
        if path.exists():
            data = json.loads(path.read_text())
            for k, v in data.items():
                if k not in _grab_registry:
                    _grab_registry[k] = _GrabInfo(**v)
            logger.info("Loaded %d entries from grab registry", len(data))
    except Exception:
        logger.warning("Could not load grab registry", exc_info=True)
    try:
        proc_path = _get_processed_path()
        if proc_path.exists():
            ids = json.loads(proc_path.read_text())
            _processed_downloads.update(ids)
            logger.info("Loaded %d processed download IDs", len(ids))
    except Exception:
        logger.warning("Could not load processed downloads", exc_info=True)
    try:
        fail_path = _get_fail_count_path()
        if fail_path.exists():
            counts = json.loads(fail_path.read_text())
            _import_fail_count.update(counts)
            logger.info("Loaded %d import fail counts", len(counts))
    except Exception:
        logger.warning("Could not load import fail counts", exc_info=True)
    _registry_loaded = True


def ensure_registry_loaded() -> None:
    """Ensure the grab/processed registries are loaded from disk.

    Safe to call multiple times — only loads once per process.
    """
    if not _registry_loaded:
        _load_registry()


def get_grab_info(download_id: str) -> _GrabInfo | None:
    """Look up grab metadata for a download. Used by the queue API."""
    return _grab_registry.get(download_id)


def dismiss_download(download_id: str) -> None:
    """Mark a download as dismissed — hides it from the queue and monitor.

    Does NOT remove the torrent from the download client.
    """
    _processed_downloads.add(download_id)
    _grab_registry.pop(download_id, None)
    _save_registry()
    logger.info("Dismissed download %s from queue", download_id)


def is_dismissed(download_id: str) -> bool:
    """Check if a download has been dismissed or already processed."""
    return download_id in _processed_downloads


def find_download_ids_for_issue(issue_id: int) -> list[str]:
    """Reverse lookup: find all download_ids registered for a given issue."""
    ensure_registry_loaded()
    return [
        did for did, info in _grab_registry.items()
        if info.issue_id == issue_id
    ]


async def grab_release(
    db: AsyncSession,
    issue_id: int,
    download_url: str,
    title: str,
    protocol: str,
    guid: str,
    match_score: float | None = None,
    match_details: str | None = None,
) -> GrabResponse:
    # Get issue
    result = await db.execute(
        select(Issue)
        .options(selectinload(Issue.magazine))
        .where(Issue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        return GrabResponse(issue_id=issue_id, message="Issue not found")

    # Find appropriate download client
    client_record = await _select_client(db, protocol)
    if not client_record:
        return GrabResponse(
            issue_id=issue_id,
            message=f"No {protocol} download client configured",
        )

    # Send to download client
    try:
        client = _instantiate_client(client_record)
        if protocol == "torrent":
            download_id = await client.add_torrent(download_url, category="pressarr")
        else:
            download_id = await client.add_nzb(download_url, category="pressarr")

        # Register grab for later import tracking
        if download_id:
            # Clear processed/fail state so monitor_downloads() will pick it up
            # again (handles re-grabbing the same torrent that was already imported
            # or gave up on).
            if download_id in _processed_downloads:
                _processed_downloads.discard(download_id)
                logger.info(
                    "Cleared processed state for re-grabbed download %s",
                    download_id,
                )
            _import_fail_count.pop(download_id, None)

            _grab_registry[download_id] = _GrabInfo(
                issue_id=issue.id,
                magazine_id=issue.magazine_id,
            )
            _save_registry()
            logger.info(
                "Registered grab: download_id=%s → issue_id=%d, magazine_id=%d",
                download_id, issue.id, issue.magazine_id,
            )

        # Update issue status (and clear forecast flag so generate_forecasts
        # won't delete it while the download is in progress)
        issue.status = "snatched"
        issue.is_forecast = False
        await db.flush()

        # Record history event
        await create_event(
            db,
            event_type="grab",
            magazine_id=issue.magazine_id,
            issue_id=issue.id,
            details=f"Grabbed: {title}",
            data={
                "release_title": title,
                "protocol": protocol,
                "download_id": download_id,
                "download_client": client_record.name,
                "guid": guid,
                "magazine_title": issue.magazine.title if issue.magazine else None,
                "issue_number": issue.number,
                **({"match_score": round(match_score, 1)} if match_score is not None else {}),
                **({"match_details": match_details} if match_details else {}),
            },
        )

        # Invalidate smart matcher pattern cache so new grabs inform future matches
        from app.services.smart_matcher import invalidate_pattern_cache

        invalidate_pattern_cache(issue.magazine_id)

        return GrabResponse(
            issue_id=issue_id,
            download_id=download_id,
            message=f"Sent to {client_record.name}",
        )
    except Exception as e:
        logger.error("Failed to grab release: %s", e, exc_info=True)
        return GrabResponse(issue_id=issue_id, message=f"Grab failed: {e}")


async def grab_pack_release(
    db: AsyncSession,
    pack_id: int,
    download_url: str,
    title: str,
    protocol: str,
    guid: str,
) -> dict:
    """Send a pack torrent to the download client.

    Similar to grab_release() but for packs (no issue/magazine association).
    The pack_id is stored in _GrabInfo so _process_completed_item() can
    detect it and route to pack dispatch instead of single-file import.
    """
    client_record = await _select_client(db, protocol)
    if not client_record:
        return {"pack_id": pack_id, "message": f"No {protocol} download client configured"}

    try:
        client = _instantiate_client(client_record)
        if protocol == "torrent":
            download_id = await client.add_torrent(download_url, category="pressarr")
        else:
            download_id = await client.add_nzb(download_url, category="pressarr")

        if download_id:
            if download_id in _processed_downloads:
                _processed_downloads.discard(download_id)
            _import_fail_count.pop(download_id, None)

            _grab_registry[download_id] = _GrabInfo(
                issue_id=0,
                magazine_id=0,
                pack_id=pack_id,
            )
            _save_registry()
            logger.info(
                "Registered pack grab: download_id=%s → pack_id=%d",
                download_id, pack_id,
            )

        await create_event(
            db,
            event_type="grab",
            pack_id=pack_id,
            details=f"Grabbed pack: {title}",
            data={
                "release_title": title,
                "protocol": protocol,
                "download_id": download_id,
                "download_client": client_record.name,
                "guid": guid,
                "pack_id": pack_id,
            },
        )

        return {
            "pack_id": pack_id,
            "download_id": download_id,
            "message": f"Sent to {client_record.name}",
        }
    except Exception as e:
        logger.error("Failed to grab pack release: %s", e, exc_info=True)
        return {"pack_id": pack_id, "message": f"Grab failed: {e}"}


async def _select_client(db: AsyncSession, protocol: str) -> DownloadClient | None:
    result = await db.execute(
        select(DownloadClient).where(
            DownloadClient.protocol == protocol,
        ).order_by(DownloadClient.priority.asc())
    )
    return result.scalars().first()


def _instantiate_client(record: DownloadClient):
    """Instantiate a download client from the DB record.

    The DownloadClient model stores connection details as individual columns:
    host, port, use_ssl, username, password, api_key.
    """
    client_type = record.client_type.lower()

    if client_type == "deluge":
        from app.download_clients.deluge import DelugeClient
        return DelugeClient(
            host=record.host,
            port=record.port,
            password=record.password or "",
            use_ssl=record.use_ssl,
        )
    elif client_type == "qbittorrent":
        from app.download_clients.qbittorrent import QBittorrentClient
        return QBittorrentClient(
            host=record.host,
            port=record.port,
            username=record.username or "admin",
            password=record.password or "",
            use_ssl=record.use_ssl,
        )
    elif client_type == "transmission":
        from app.download_clients.transmission import TransmissionClient
        return TransmissionClient(
            host=record.host,
            port=record.port,
            username=record.username,
            password=record.password,
            use_ssl=record.use_ssl,
        )
    elif client_type == "sabnzbd":
        from app.download_clients.sabnzbd import SABnzbdClient
        return SABnzbdClient(
            host=record.host,
            port=record.port,
            api_key=record.api_key or "",
            use_ssl=record.use_ssl,
        )
    elif client_type == "nzbget":
        from app.download_clients.nzbget import NZBGetClient
        return NZBGetClient(
            host=record.host,
            port=record.port,
            username=record.username or "nzbget",
            password=record.password or "",
            use_ssl=record.use_ssl,
        )
    else:
        raise ValueError(f"Unknown client type: {client_type}")


def _instantiate_client_from_dict(cfg: dict):
    """Instantiate a download client from an eagerly-loaded config dict.

    Used by monitor_downloads and trigger_import to avoid lazy-loading
    ORM attributes after a session rollback (MissingGreenlet).
    """
    client_type = cfg["client_type"].lower()

    if client_type == "deluge":
        from app.download_clients.deluge import DelugeClient
        return DelugeClient(
            host=cfg["host"], port=cfg["port"],
            password=cfg["password"] or "", use_ssl=cfg["use_ssl"],
        )
    elif client_type == "qbittorrent":
        from app.download_clients.qbittorrent import QBittorrentClient
        return QBittorrentClient(
            host=cfg["host"], port=cfg["port"],
            username=cfg["username"] or "admin",
            password=cfg["password"] or "", use_ssl=cfg["use_ssl"],
        )
    elif client_type == "transmission":
        from app.download_clients.transmission import TransmissionClient
        return TransmissionClient(
            host=cfg["host"], port=cfg["port"],
            username=cfg["username"], password=cfg["password"],
            use_ssl=cfg["use_ssl"],
        )
    elif client_type == "sabnzbd":
        from app.download_clients.sabnzbd import SABnzbdClient
        return SABnzbdClient(
            host=cfg["host"], port=cfg["port"],
            api_key=cfg["api_key"] or "", use_ssl=cfg["use_ssl"],
        )
    elif client_type == "nzbget":
        from app.download_clients.nzbget import NZBGetClient
        return NZBGetClient(
            host=cfg["host"], port=cfg["port"],
            username=cfg["username"] or "nzbget",
            password=cfg["password"] or "", use_ssl=cfg["use_ssl"],
        )
    else:
        raise ValueError(f"Unknown client type: {client_type}")


def _apply_path_mapping(path_str: str, remote_path: str | None, local_path: str | None) -> str:
    """Apply remote→local path mapping (like Radarr/Sonarr Remote Path Mapping).

    If the download client reports save_path=/data/complete and the mapping is
    remote=/data/complete → local=/downloads, the result is /downloads.
    """
    if not remote_path or not local_path:
        return path_str
    # Normalize: ensure trailing slash for prefix matching
    remote = remote_path.rstrip("/") + "/"
    if path_str.startswith(remote) or path_str.rstrip("/") + "/" == remote:
        mapped = path_str.replace(remote_path.rstrip("/"), local_path.rstrip("/"), 1)
        logger.info("Path mapping: %s → %s", path_str, mapped)
        return mapped
    return path_str


def _resolve_save_path(item, remote_path: str | None = None, local_path: str | None = None) -> Path | None:
    """Resolve the exact file/folder path for a torrent item.

    Strict mode: returns ONLY base_path/torrent_name.
    No fallback, no directory scanning. If the exact path doesn't exist,
    returns None so the caller reports an error.
    """
    mapped_save_path = _apply_path_mapping(item.save_path, remote_path, local_path)
    base_path = Path(mapped_save_path)
    torrent_name = item.name if item.name else None

    if not torrent_name:
        logger.warning("No torrent name provided, cannot resolve path")
        return None

    torrent_path = base_path / torrent_name
    if torrent_path.exists():
        return torrent_path

    logger.warning(
        "Torrent file not found at exact path: %s "
        "(base=%s, name=%s). Check volume mounts and Remote Path Mapping.",
        torrent_path, base_path, torrent_name,
    )
    return None


def _collect_importable_files(save_path: Path) -> list[Path]:
    """Return the torrent file(s) to import.

    - If save_path is a supported file → return it directly.
    - If save_path is a directory (multi-file torrent) → return only
      the supported files inside that specific torrent folder.
    """
    supported = {".pdf", ".epub", ".cbr", ".cbz"}
    if save_path.is_file():
        if save_path.suffix.lower() in supported:
            return [save_path]
        return []
    if save_path.is_dir():
        return [f for f in save_path.rglob("*") if f.is_file() and f.suffix.lower() in supported]
    return []


async def monitor_downloads(db: AsyncSession) -> None:
    """Poll all download clients, detect completed downloads, trigger import."""
    # Ensure grab registry + processed set are loaded from disk
    ensure_registry_loaded()

    result = await db.execute(select(DownloadClient))
    clients = result.scalars().all()

    # Eagerly read all client attributes to avoid lazy-loading after rollback
    client_configs = [
        {
            "name": cr.name,
            "client_type": cr.client_type,
            "host": cr.host,
            "port": cr.port,
            "use_ssl": cr.use_ssl,
            "username": cr.username,
            "password": cr.password,
            "api_key": cr.api_key,
            "category": cr.category,
            "remote_path": cr.remote_path,
            "local_path": cr.local_path,
        }
        for cr in clients
    ]

    for cfg in client_configs:
        try:
            client = _instantiate_client_from_dict(cfg)
            items = await client.get_all(category=cfg["category"])

            # Collect download_ids seen from get_all so we know which
            # grab_registry entries were NOT returned (label missing, etc.)
            seen_download_ids: set[str] = set()

            for item in items:
                if item.download_id:
                    seen_download_ids.add(item.download_id)
                # Skip already-processed/dismissed downloads entirely
                if item.download_id and item.download_id in _processed_downloads:
                    continue
                logger.debug(
                    "Monitor: %s status=%s save_path=%s name=%s",
                    item.download_id, item.status, item.save_path, item.name,
                )
                if item.status == "completed" and item.save_path:
                    await _process_completed_item(db, item, cfg)

            # Fallback: check grab_registry entries not returned by get_all.
            # This handles cases where the Label plugin is not available or
            # the label was not applied to the torrent.
            for download_id, grab_info in list(_grab_registry.items()):
                if download_id in seen_download_ids:
                    continue
                if download_id in _processed_downloads:
                    continue
                try:
                    item = await client.get_status(download_id)
                    if not item:
                        continue
                    logger.info(
                        "Monitor (fallback): %s status=%s save_path=%s name=%s",
                        item.download_id, item.status, item.save_path, item.name,
                    )
                    if item.status == "completed" and item.save_path:
                        await _process_completed_item(db, item, cfg)
                except Exception:
                    logger.debug(
                        "Monitor: fallback check failed for %s", download_id, exc_info=True,
                    )

        except Exception:
            logger.warning(
                "Monitor error for %s", cfg["name"], exc_info=True
            )


async def _process_completed_item(db: AsyncSession, item, cfg: dict) -> None:
    """Process a single completed download item (import + commit)."""
    # Check if this download belongs to a pack
    grab = _grab_registry.get(item.download_id) if item.download_id else None
    if grab and grab.pack_id:
        await _process_pack_download(db, item, grab, cfg)
        return

    try:
        import_result = await _try_import_item(
            db, item,
            remote_path=cfg["remote_path"],
            local_path=cfg["local_path"],
        )
        # Commit after each successful import to isolate DB state
        if import_result.get("success"):
            await db.commit()
            # Broadcast WebSocket update so frontend refreshes
            try:
                from app.api.v1.websocket import manager as ws_manager
                await ws_manager.broadcast(
                    "library:updated",
                    {"magazineId": import_result.get("magazine_id")},
                )
            except Exception:
                logger.debug("WebSocket broadcast failed", exc_info=True)
    except Exception:
        logger.warning(
            "Monitor: import failed for %s", item.download_id, exc_info=True
        )
        try:
            await db.rollback()
        except Exception:
            pass


async def _process_pack_download(
    db: AsyncSession, item, grab: _GrabInfo, cfg: dict
) -> None:
    """Process a completed pack download — dispatch files to magazines."""
    from app.dependencies import get_config
    from app.services.pack_service import (
        collect_pack_files,
        dispatch_files,
        get_pack,
        preview_dispatch,
    )

    pack_id = grab.pack_id
    logger.info("Monitor: processing pack download %s for pack_id=%d", item.download_id, pack_id)

    save_path = _resolve_save_path(
        item, remote_path=cfg["remote_path"], local_path=cfg["local_path"]
    )
    if not save_path:
        logger.warning("Monitor: pack download path not found for %s", item.download_id)
        return

    files = collect_pack_files(save_path)
    if not files:
        logger.warning("Monitor: no supported files in pack download %s", save_path)
        if item.download_id:
            _processed_downloads.add(item.download_id)
            _grab_registry.pop(item.download_id, None)
            _save_registry()
        return

    pack = await get_pack(db, pack_id)
    if not pack:
        logger.warning("Monitor: pack %d not found, falling back to normal import", pack_id)
        return

    config = get_config()

    if pack.auto_import:
        # Auto dispatch: preview then import automatically
        preview = await preview_dispatch(db, pack_id, files, pack.rules)
        assignments = [
            {
                "filename": f["filename"],
                "magazine_id": f["matched_magazine_id"],
                "skip": f["excluded"] or not f["matched_magazine_id"],
            }
            for f in preview
        ]
        file_paths_by_name = {f.name: f for f in files}
        results = await dispatch_files(db, assignments, file_paths_by_name, config)
        imported = sum(1 for r in results if r.get("success"))
        logger.info(
            "Monitor: pack auto-dispatch completed — %d/%d files imported",
            imported, len(results),
        )
        await db.commit()

        # Create history event
        await create_event(
            db,
            event_type="import",
            pack_id=pack_id,
            details=f"Pack auto-import: {imported}/{len(results)} files",
            data={
                "pack_name": pack.name,
                "total_files": len(results),
                "imported_files": imported,
                "results": results[:20],
            },
        )
        await db.commit()

        try:
            from app.api.v1.websocket import manager as ws_manager
            await ws_manager.broadcast("library:updated", {})
        except Exception:
            pass
    else:
        # Manual dispatch: send preview to frontend via WebSocket
        preview = await preview_dispatch(db, pack_id, files, pack.rules)
        matched = sum(1 for f in preview if f["matched_magazine_id"])
        excluded = sum(1 for f in preview if f["excluded"])
        try:
            from app.api.v1.websocket import manager as ws_manager
            await ws_manager.broadcast(
                "pack:dispatch_ready",
                {
                    "pack_id": pack_id,
                    "pack_name": pack.name,
                    "download_id": item.download_id,
                    "torrent_name": item.name or "",
                    "total_files": len(preview),
                    "matched_files": matched,
                    "excluded_files": excluded,
                    "unmatched_files": len(preview) - matched - excluded,
                    "files": preview,
                },
            )
        except Exception:
            logger.warning("WebSocket broadcast failed for pack dispatch", exc_info=True)
        logger.info(
            "Monitor: pack dispatch ready — %d files, %d matched, %d excluded",
            len(preview), matched, excluded,
        )
        # Don't mark as processed yet — wait for user dispatch action
        return

    # Mark as processed after auto-import
    if item.download_id:
        _processed_downloads.add(item.download_id)
        _grab_registry.pop(item.download_id, None)
        _import_fail_count.pop(item.download_id, None)
        _save_registry()


async def _try_import_item(
    db: AsyncSession,
    item,
    force: bool = False,
    remote_path: str | None = None,
    local_path: str | None = None,
    override_issue_id: int | None = None,
    override_magazine_id: int | None = None,
) -> dict:
    """Try to import a completed download item. Returns import result dict."""
    from app.dependencies import get_config
    from app.services.import_service import process_downloaded_file

    # Skip already-processed downloads (unless forced)
    if not force and item.download_id and item.download_id in _processed_downloads:
        logger.debug("Skipping already-processed download %s", item.download_id)
        return {"success": False, "message": "Already processed"}

    config = get_config()
    save_path = _resolve_save_path(item, remote_path=remote_path, local_path=local_path)

    logger.info(
        "Monitor: completed download %s — resolved_path=%s, name=%s, "
        "original_save_path=%s, remote_path=%s, local_path=%s",
        item.download_id, save_path, item.name,
        item.save_path, remote_path, local_path,
    )

    # Resolve grab info for history events
    grab = _grab_registry.get(item.download_id) if item.download_id else None
    hist_magazine_id = override_magazine_id or (grab.magazine_id if grab else None)
    hist_issue_id = override_issue_id or (grab.issue_id if grab else None)

    if not save_path:
        # Track consecutive failures — log WARNING only the first few times,
        # then switch to DEBUG to avoid spamming the log every 30 seconds.
        fail_count = _import_fail_count.get(item.download_id, 0) + 1
        _import_fail_count[item.download_id] = fail_count
        _save_registry()
        if fail_count >= MAX_IMPORT_FAILURES:
            logger.warning(
                "Monitor: giving up on download %s after %d failed path resolutions. "
                "Check volume mounts or Remote Path Mapping.",
                item.download_id, fail_count,
            )
            mapped = _apply_path_mapping(item.save_path, remote_path, local_path)
            expected = f"{mapped}/{item.name}" if item.name else mapped
            await create_event(
                db, "error",
                magazine_id=hist_magazine_id,
                issue_id=hist_issue_id,
                details=f"Import failed: file not accessible after {fail_count} attempts",
                data={
                    "error": "path_not_found",
                    "download_id": item.download_id,
                    "download_name": item.name,
                    "expected_path": expected,
                    "remote_path": remote_path,
                    "local_path": local_path,
                    "attempts": fail_count,
                },
            )
            _processed_downloads.add(item.download_id)
            _import_fail_count.pop(item.download_id, None)
            _save_registry()
            return {"success": False, "message": f"Gave up after {fail_count} path resolution failures"}
        log_fn = logger.warning if fail_count <= 3 else logger.debug
        log_fn(
            "Monitor: path %s (+ name=%s) does not exist in container! "
            "Check volume mounts or Remote Path Mapping. "
            "Deluge save_path=%s, remote_path=%s, local_path=%s (attempt #%d)",
            item.save_path, item.name, item.save_path, remote_path, local_path,
            fail_count,
        )
        mapped = _apply_path_mapping(item.save_path, remote_path, local_path)
        expected = f"{mapped}/{item.name}" if item.name else mapped
        return {
            "success": False,
            "message": (
                f"File not found: {expected} "
                f"(remote_path={remote_path!r}, local_path={local_path!r})"
            ),
        }

    files = _collect_importable_files(save_path)
    logger.info("Monitor: found %d importable files: %s", len(files), [f.name for f in files])

    if not files:
        logger.warning("Monitor: no supported files found in %s", save_path)
        await create_event(
            db, "error",
            magazine_id=hist_magazine_id,
            issue_id=hist_issue_id,
            details="Import failed: no supported files in download",
            data={
                "error": "no_supported_files",
                "download_id": item.download_id,
                "download_name": item.name,
                "path": str(save_path),
            },
        )
        # Mark as processed so we don't retry every 30 seconds
        if item.download_id:
            _processed_downloads.add(item.download_id)
            _save_registry()
        return {"success": False, "message": f"No supported files in {save_path}"}

    # Resolve issue/magazine association:
    # 1. Override params (from queue item metadata) take priority
    # 2. Then grab registry (from grab time)
    # 3. Fallback: filename parsing in process_downloaded_file
    issue_id = override_issue_id
    magazine_id = override_magazine_id

    if not issue_id:
        grab = _grab_registry.get(item.download_id) if item.download_id else None
        if grab:
            issue_id = grab.issue_id
            magazine_id = grab.magazine_id

    if issue_id:
        logger.info(
            "Monitor: issue association — issue_id=%d, magazine_id=%s (source=%s)",
            issue_id, magazine_id,
            "queue_item" if override_issue_id else "grab_registry",
        )
    else:
        logger.info("Monitor: no issue association, will use filename parsing")

    imported_any = False
    last_result = {}
    for f in files:
        result_info = await process_downloaded_file(
            db, f, config,
            magazine_id=magazine_id,
            issue_id=issue_id,
        )
        logger.info(
            "Monitor: import result for %s: %s",
            f.name, result_info,
        )
        last_result = result_info
        if result_info.get("success"):
            imported_any = True

    # Track business-logic failures (e.g. "not a quality upgrade")
    if not imported_any and item.download_id:
        fail_count = _import_fail_count.get(item.download_id, 0) + 1
        _import_fail_count[item.download_id] = fail_count
        _save_registry()
        if fail_count >= MAX_IMPORT_FAILURES:
            logger.warning(
                "Monitor: giving up on download %s after %d failed import attempts: %s",
                item.download_id, fail_count, last_result.get("message", "unknown"),
            )
            await create_event(
                db, "error",
                magazine_id=hist_magazine_id,
                issue_id=hist_issue_id,
                details=f"Import failed: {last_result.get('message', 'unknown reason')}",
                data={
                    "error": "import_failed",
                    "download_id": item.download_id,
                    "download_name": item.name,
                    "reason": last_result.get("message", "unknown"),
                    "attempts": fail_count,
                },
            )
            _processed_downloads.add(item.download_id)
            _import_fail_count.pop(item.download_id, None)
            _save_registry()

    # Mark as processed and clean up registry
    # (download stays in client for seeding / user management)
    if imported_any and item.download_id:
        _processed_downloads.add(item.download_id)
        _grab_registry.pop(item.download_id, None)
        _import_fail_count.pop(item.download_id, None)
        _save_registry()

    # Always include magazine_id in result for WebSocket broadcast
    if magazine_id:
        last_result["magazine_id"] = magazine_id

    return last_result


async def trigger_import(
    db: AsyncSession,
    download_id: str,
    issue_id: int | None = None,
    magazine_id: int | None = None,
) -> dict:
    """Manually trigger import for a specific download by its ID.

    When issue_id/magazine_id are provided (from the queue item metadata),
    they take priority over the grab registry lookup.
    """
    # Load all clients upfront to avoid lazy-loading issues after rollback
    result = await db.execute(select(DownloadClient))
    clients = list(result.scalars().all())
    # Eagerly read all attributes we need before any potential rollback
    client_configs = [
        {
            "name": cr.name,
            "client_type": cr.client_type,
            "host": cr.host,
            "port": cr.port,
            "use_ssl": cr.use_ssl,
            "username": cr.username,
            "password": cr.password,
            "api_key": cr.api_key,
            "remote_path": cr.remote_path,
            "local_path": cr.local_path,
        }
        for cr in clients
    ]

    for cfg in client_configs:
        try:
            client = _instantiate_client_from_dict(cfg)
            status = await client.get_status(download_id)
            if status and status.save_path:
                # Rollback any failed transaction before attempting import
                try:
                    await db.rollback()
                except Exception:
                    pass
                return await _try_import_item(
                    db, status, force=True,
                    remote_path=cfg["remote_path"],
                    local_path=cfg["local_path"],
                    override_issue_id=issue_id,
                    override_magazine_id=magazine_id,
                )
        except Exception:
            logger.warning(
                "trigger_import error for %s", cfg["name"], exc_info=True
            )
            # Ensure session is usable for next iteration
            try:
                await db.rollback()
            except Exception:
                pass

    return {"success": False, "message": f"Download {download_id} not found in any client"}


async def _resolve_download_path(db: AsyncSession, download_id: str) -> Path | None:
    """Resolve the filesystem path for a download by its ID.

    Queries all configured download clients to find the download and return
    its resolved save path. Used by pack dispatch endpoints.
    """
    result = await db.execute(select(DownloadClient))
    clients = result.scalars().all()
    client_configs = [
        {
            "client_type": cr.client_type,
            "host": cr.host,
            "port": cr.port,
            "use_ssl": cr.use_ssl,
            "username": cr.username,
            "password": cr.password,
            "api_key": cr.api_key,
            "remote_path": cr.remote_path,
            "local_path": cr.local_path,
        }
        for cr in clients
    ]

    for cfg in client_configs:
        try:
            client = _instantiate_client_from_dict(cfg)
            status = await client.get_status(download_id)
            if status and status.save_path:
                return _resolve_save_path(
                    status,
                    remote_path=cfg["remote_path"],
                    local_path=cfg["local_path"],
                )
        except Exception:
            logger.debug("_resolve_download_path: error for client", exc_info=True)

    return None


async def cleanup_orphaned_snatched(db: AsyncSession) -> int:
    """Reset issues stuck in 'snatched' for >48h with no active download.

    Returns the number of issues reset to 'wanted'.
    """
    from datetime import UTC, datetime, timedelta

    from app.models.history import History

    ensure_registry_loaded()
    cutoff = datetime.now(UTC) - timedelta(hours=48)

    # Find all snatched + monitored issues
    result = await db.execute(
        select(Issue).where(
            Issue.status == "snatched",
            Issue.monitored == True,  # noqa: E712
        )
    )
    snatched_issues = list(result.scalars().all())
    if not snatched_issues:
        return 0

    # Collect all active download_ids from clients
    client_result = await db.execute(select(DownloadClient))
    clients = client_result.scalars().all()
    active_download_ids: set[str] = set()

    for cr in clients:
        try:
            client = _instantiate_client(cr)
            items = await client.get_all(category=cr.category)
            for item in items:
                if item.download_id:
                    active_download_ids.add(item.download_id)
        except Exception:
            logger.debug("cleanup: failed to poll %s", cr.name, exc_info=True)

    reset_count = 0
    for issue in snatched_issues:
        download_ids = find_download_ids_for_issue(issue.id)
        has_active = any(did in active_download_ids for did in download_ids)
        has_registry = len(download_ids) > 0

        if not has_active and not has_registry:
            # No record at all — orphaned
            issue.status = "wanted"
            reset_count += 1
            logger.info(
                "Reset orphaned snatched issue id=%d (no registry entry) to wanted",
                issue.id,
            )
        elif has_registry and not has_active:
            # Registry entry exists but download gone from client — check age
            grab_event = (await db.execute(
                select(History).where(
                    History.issue_id == issue.id,
                    History.event_type == "grab",
                ).order_by(History.date.desc()).limit(1)
            )).scalars().first()
            grab_date = grab_event.date if grab_event else None
            if grab_date and hasattr(grab_date, "tzinfo") and grab_date.tzinfo is None:
                grab_date = grab_date.replace(tzinfo=UTC)
            if not grab_event or (grab_date and grab_date < cutoff):
                issue.status = "wanted"
                for did in download_ids:
                    _grab_registry.pop(did, None)
                _save_registry()
                reset_count += 1
                logger.info(
                    "Reset orphaned snatched issue id=%d (grab >48h, download gone) to wanted",
                    issue.id,
                )

    if reset_count:
        await db.flush()

    return reset_count
