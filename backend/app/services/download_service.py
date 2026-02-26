"""Download management service."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.download_client import DownloadClient
from app.models.issue import Issue
from app.schemas.search import GrabResponse
from app.services.history_service import create_event

logger = logging.getLogger(__name__)


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
                if item.status == "completed" and item.save_path:
                    from pathlib import Path
                    from app.services.import_service import process_downloaded_file
                    from app.dependencies import get_config

                    config = get_config()
                    save_path = Path(item.save_path)
                    files = (
                        list(save_path.iterdir())
                        if save_path.is_dir()
                        else [save_path]
                    )
                    for f in files:
                        if f.suffix.lower() in {".pdf", ".epub", ".cbr", ".cbz"}:
                            await process_downloaded_file(db, f, config)
        except Exception:
            logger.warning(
                "Monitor error for %s", client_record.name, exc_info=True
            )
