"""Download management service."""
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.download_client import DownloadClient
from app.models.issue import Issue
from app.schemas.search import GrabResponse
from app.services.history_service import create_event

logger = logging.getLogger(__name__)


@dataclass
class _GrabInfo:
    """Tracks which issue a torrent/usenet download belongs to."""
    issue_id: int
    magazine_id: int


# download_id → GrabInfo — populated at grab time, consumed at import time
_grab_registry: dict[str, _GrabInfo] = {}

# download_ids that have already been imported (prevents re-processing)
_processed_downloads: set[str] = set()


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


async def monitor_downloads(db: AsyncSession) -> None:
    """Poll all download clients, detect completed downloads, trigger import."""
    result = await db.execute(select(DownloadClient))
    clients = result.scalars().all()

    for client_record in clients:
        try:
            client = _instantiate_client(client_record)
            items = await client.get_all(category=client_record.category)
            for item in items:
                logger.debug(
                    "Monitor: %s status=%s save_path=%s name=%s",
                    item.download_id, item.status, item.save_path, item.name,
                )
                if item.status == "completed" and item.save_path:
                    # Skip already-processed downloads
                    if item.download_id and item.download_id in _processed_downloads:
                        continue

                    from pathlib import Path

                    from app.dependencies import get_config
                    from app.services.import_service import process_downloaded_file

                    config = get_config()
                    # save_path from Deluge is the parent directory;
                    # combine with torrent name to find the actual file/folder
                    base_path = Path(item.save_path)
                    torrent_path = base_path / item.name if item.name else base_path
                    # Use torrent-specific path if it exists, otherwise fall back
                    if torrent_path.exists():
                        save_path = torrent_path
                    else:
                        save_path = base_path
                    logger.info(
                        "Monitor: completed download %s — save_path=%s, exists=%s, is_dir=%s",
                        item.download_id, save_path, save_path.exists(), save_path.is_dir() if save_path.exists() else "N/A",
                    )
                    if not save_path.exists():
                        logger.warning(
                            "Monitor: path %s does not exist in container! Check volume mounts.",
                            save_path,
                        )
                        continue
                    files = (
                        list(save_path.iterdir())
                        if save_path.is_dir()
                        else [save_path]
                    )
                    logger.info("Monitor: found files to check: %s", [str(f) for f in files])

                    # Look up grab registry for issue association
                    grab = _grab_registry.get(item.download_id) if item.download_id else None
                    issue_id = grab.issue_id if grab else None
                    magazine_id = grab.magazine_id if grab else None

                    imported_any = False
                    for f in files:
                        if f.suffix.lower() in {".pdf", ".epub", ".cbr", ".cbz"}:
                            result_info = await process_downloaded_file(
                                db, f, config,
                                magazine_id=magazine_id,
                                issue_id=issue_id,
                            )
                            if result_info.get("success"):
                                imported_any = True

                    # Mark as processed and clean up registry
                    # (download stays in client for seeding / user management)
                    if imported_any and item.download_id:
                        _processed_downloads.add(item.download_id)
                        _grab_registry.pop(item.download_id, None)
        except Exception:
            logger.warning(
                "Monitor error for %s", client_record.name, exc_info=True
            )
