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
    """Tracks which issue a torrent/usenet download belongs to."""
    issue_id: int
    magazine_id: int


# download_id → GrabInfo — populated at grab time, consumed at import time
_grab_registry: dict[str, _GrabInfo] = {}

# download_ids that have already been imported (prevents re-processing)
_processed_downloads: set[str] = set()


def _get_registry_path() -> Path:
    """Get the path for the persistent grab registry file."""
    global _GRAB_REGISTRY_PATH
    if _GRAB_REGISTRY_PATH is None:
        from app.dependencies import get_config
        config = get_config()
        _GRAB_REGISTRY_PATH = config.config_path.parent / "grab_registry.json"
    return _GRAB_REGISTRY_PATH


def _save_registry() -> None:
    """Persist grab registry to disk."""
    try:
        path = _get_registry_path()
        data = {k: asdict(v) for k, v in _grab_registry.items()}
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        logger.debug("Could not save grab registry", exc_info=True)


def _load_registry() -> None:
    """Load grab registry from disk on startup."""
    try:
        path = _get_registry_path()
        if path.exists():
            data = json.loads(path.read_text())
            for k, v in data.items():
                if k not in _grab_registry:
                    _grab_registry[k] = _GrabInfo(**v)
            logger.info("Loaded %d entries from grab registry", len(data))
    except Exception:
        logger.debug("Could not load grab registry", exc_info=True)


def get_grab_info(download_id: str) -> _GrabInfo | None:
    """Look up grab metadata for a download. Used by the queue API."""
    return _grab_registry.get(download_id)


async def grab_release(
    db: AsyncSession,
    issue_id: int,
    download_url: str,
    title: str,
    protocol: str,
    guid: str,
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
            _grab_registry[download_id] = _GrabInfo(
                issue_id=issue.id,
                magazine_id=issue.magazine_id,
            )
            _save_registry()
            logger.info(
                "Registered grab: download_id=%s → issue_id=%d, magazine_id=%d",
                download_id, issue.id, issue.magazine_id,
            )

        # Update issue status
        issue.status = "snatched"
        await db.flush()

        # Record history event
        await create_event(
            db,
            event_type="grab",
            magazine_id=issue.magazine_id,
            issue_id=issue.id,
            details=f"Grabbed: {title}",
        )

        return GrabResponse(
            issue_id=issue_id,
            download_id=download_id,
            message=f"Sent to {client_record.name}",
        )
    except Exception as e:
        logger.error("Failed to grab release: %s", e, exc_info=True)
        return GrabResponse(issue_id=issue_id, message=f"Grab failed: {e}")


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
    # Ensure grab registry is loaded from disk
    if not _grab_registry:
        _load_registry()

    result = await db.execute(select(DownloadClient))
    clients = result.scalars().all()

    for client_record in clients:
        try:
            client = _instantiate_client(client_record)
            items = await client.get_all(category=client_record.category)
            for item in items:
                log_fn = logger.info if item.status == "completed" else logger.debug
                log_fn(
                    "Monitor: %s status=%s save_path=%s name=%s",
                    item.download_id, item.status, item.save_path, item.name,
                )
                if item.status == "completed" and item.save_path:
                    try:
                        await _try_import_item(
                            db, item,
                            remote_path=client_record.remote_path,
                            local_path=client_record.local_path,
                        )
                    except Exception:
                        logger.warning(
                            "Monitor: import failed for %s", item.download_id, exc_info=True
                        )
                        try:
                            await db.rollback()
                        except Exception:
                            pass
        except Exception:
            logger.warning(
                "Monitor error for %s", client_record.name, exc_info=True
            )


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

    if not save_path:
        logger.warning(
            "Monitor: path %s (+ name=%s) does not exist in container! "
            "Check volume mounts or Remote Path Mapping. "
            "Deluge save_path=%s, remote_path=%s, local_path=%s",
            item.save_path, item.name, item.save_path, remote_path, local_path,
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

    # Mark as processed and clean up registry
    # (download stays in client for seeding / user management)
    if imported_any and item.download_id:
        _processed_downloads.add(item.download_id)
        _grab_registry.pop(item.download_id, None)
        _save_registry()

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
            "record": cr,
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
            client = _instantiate_client(cfg["record"])
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
