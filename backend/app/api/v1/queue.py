"""Download queue API endpoints."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.download_client import DownloadClient
from app.schemas.queue import QueueBulkDeleteRequest, QueueItemResource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/queue", tags=["Queue"])


async def _get_queue_items(db: AsyncSession) -> list[QueueItemResource]:
    """Poll all download clients for pressarr-category items."""
    result = await db.execute(select(DownloadClient))
    clients = result.scalars().all()

    items = []
    item_id = 0

    for client_record in clients:
        try:
            client = _instantiate_client(client_record)
            status_list = await client.get_all(category=client_record.category)

            for entry in status_list:
                item_id += 1
                size_left = int(entry.size * (1.0 - entry.progress)) if entry.size else 0
                items.append(QueueItemResource(
                    id=item_id,
                    title=entry.name,
                    status=entry.status,
                    protocol=client_record.protocol,
                    download_client=client_record.name,
                    download_client_id=client_record.id,
                    download_id=entry.download_id,
                    size=entry.size,
                    size_left=size_left,
                    progress=round(entry.progress * 100, 1),
                    speed=entry.speed,
                    eta=entry.eta,
                ))
        except Exception:
            logger.warning(
                "Failed to poll queue for %s", client_record.name, exc_info=True
            )

    return items


def _instantiate_client(record: DownloadClient):
    """Create a download client instance from a DB record."""
    client_type = record.client_type.lower()

    if client_type == "deluge":
        from app.download_clients.deluge import DelugeClient
        return DelugeClient(host=record.host, port=record.port, password=record.password or "", use_ssl=record.use_ssl)
    elif client_type == "qbittorrent":
        from app.download_clients.qbittorrent import QBittorrentClient
        return QBittorrentClient(host=record.host, port=record.port, username=record.username or "admin", password=record.password or "", use_ssl=record.use_ssl)
    elif client_type == "transmission":
        from app.download_clients.transmission import TransmissionClient
        return TransmissionClient(host=record.host, port=record.port, username=record.username, password=record.password, use_ssl=record.use_ssl)
    elif client_type == "sabnzbd":
        from app.download_clients.sabnzbd import SABnzbdClient
        return SABnzbdClient(host=record.host, port=record.port, api_key=record.api_key or "", use_ssl=record.use_ssl)
    elif client_type == "nzbget":
        from app.download_clients.nzbget import NZBGetClient
        return NZBGetClient(host=record.host, port=record.port, username=record.username or "nzbget", password=record.password or "", use_ssl=record.use_ssl)
    else:
        raise ValueError(f"Unknown client type: {client_type}")


@router.get("", response_model=list[QueueItemResource])
async def get_queue(db: AsyncSession = Depends(get_db)):
    """Get current download queue from all clients."""
    return await _get_queue_items(db)


@router.delete("/{item_id}")
async def remove_from_queue(
    item_id: int,
    blocklist: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Remove an item from the queue (cancel download)."""
    items = await _get_queue_items(db)
    item = next((i for i in items if i.id == item_id), None)

    if item and item.download_id and item.download_client_id:
        client_result = await db.execute(
            select(DownloadClient).where(DownloadClient.id == item.download_client_id)
        )
        client_record = client_result.scalars().first()
        if client_record:
            try:
                client = _instantiate_client(client_record)
                await client.remove(item.download_id)
            except Exception:
                logger.warning("Failed to remove download %s", item.download_id, exc_info=True)

        if blocklist and item.title:
            from app.services.history_service import add_to_blocklist
            await add_to_blocklist(
                db,
                release_title=item.title,
                magazine_id=item.magazine_id,
                issue_id=item.issue_id,
                reason="Removed from queue",
            )

    return {}


@router.delete("/bulk")
async def bulk_remove_from_queue(
    body: QueueBulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Remove multiple items from the queue."""
    for item_id in body.ids:
        await remove_from_queue(item_id, blocklist=body.blocklist, db=db)
    return {}
