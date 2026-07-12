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
    """Poll all download clients + direct download tracker for queue items."""
    from app.services.direct_download_tracker import tracker as dd_tracker

    # Clean up old completed/failed downloads
    dd_tracker.cleanup_completed(max_age_seconds=300)

    result = await db.execute(select(DownloadClient))
    clients = result.scalars().all()

    items = []
    item_id = 0

    # 1. Regular download clients (torrent/usenet)
    # Collect all download_ids first, then batch-load issue/magazine metadata
    from app.services.download_service import ensure_registry_loaded, get_grab_info, is_dismissed

    # Ensure processed-downloads set is loaded from disk (survives backend reload)
    ensure_registry_loaded()

    pending_enrichments: dict[int, tuple[int, int]] = {}  # item_index → (issue_id, magazine_id)

    for client_record in clients:
        try:
            client = _instantiate_client(client_record)
            status_list = await client.get_all(category=client_record.category)

            for entry in status_list:
                # Skip downloads that have been dismissed or already imported
                if entry.download_id and is_dismissed(entry.download_id):
                    continue

                item_id += 1
                size_left = int(entry.size * (1.0 - entry.progress)) if entry.size else 0
                resource = QueueItemResource(
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
                )
                items.append(resource)

                # Check grab registry for issue association
                if entry.download_id:
                    grab = get_grab_info(entry.download_id)
                    if grab:
                        pending_enrichments[len(items) - 1] = (grab.issue_id, grab.magazine_id)

        except Exception:
            logger.warning(
                "Failed to poll queue for %s", client_record.name, exc_info=True
            )

    # Batch-load issue + magazine metadata for all grab-registered downloads
    if pending_enrichments:
        from sqlalchemy.orm import selectinload

        from app.models.issue import Issue

        issue_ids = [eid for eid, _ in pending_enrichments.values()]
        issue_result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.magazine))
            .where(Issue.id.in_(issue_ids))
        )
        issues_by_id = {iss.id: iss for iss in issue_result.scalars().all()}

        for idx, (iss_id, mag_id) in pending_enrichments.items():
            resource = items[idx]
            issue = issues_by_id.get(iss_id)
            if issue:
                resource.issue_id = issue.id
                resource.magazine_id = issue.magazine_id
                resource.issue_number = issue.number
                if issue.magazine:
                    resource.magazine_title = issue.magazine.title

    # 2. Direct downloads (Internet Archive, Anna's Archive)
    for tracked in dd_tracker.get_all():
        s = tracked.status
        item_id += 1
        size_left = int(s.size * (1.0 - s.progress)) if s.size else 0
        items.append(QueueItemResource(
            id=item_id,
            title=s.name,
            status=s.status,
            protocol=tracked.protocol,
            download_client=tracked.source,
            download_client_id=None,
            download_id=s.download_id,
            size=s.size,
            size_left=size_left,
            progress=round(s.progress * 100, 1),
            speed=s.speed,
            eta=s.eta,
            magazine_id=tracked.magazine_id,
            magazine_title=tracked.magazine_title,
            issue_id=tracked.issue_id,
            issue_number=tracked.issue_number,
            added=tracked.added,
            error_message=tracked.error_message,
        ))

    return items


def _instantiate_client(record: DownloadClient):
    """Create a download client instance from a DB record."""
    client_type = record.client_type.lower()

    if client_type == "deluge":
        from app.download_clients.deluge import DelugeClient
        return DelugeClient(
            host=record.host, port=record.port, password=record.password or "", use_ssl=record.use_ssl,
        )
    elif client_type == "qbittorrent":
        from app.download_clients.qbittorrent import QBittorrentClient
        return QBittorrentClient(
            host=record.host, port=record.port, username=record.username or "admin",
            password=record.password or "", use_ssl=record.use_ssl,
        )
    elif client_type == "transmission":
        from app.download_clients.transmission import TransmissionClient
        return TransmissionClient(
            host=record.host, port=record.port, username=record.username,
            password=record.password, use_ssl=record.use_ssl,
        )
    elif client_type == "sabnzbd":
        from app.download_clients.sabnzbd import SABnzbdClient
        return SABnzbdClient(
            host=record.host, port=record.port, api_key=record.api_key or "", use_ssl=record.use_ssl,
        )
    elif client_type == "nzbget":
        from app.download_clients.nzbget import NZBGetClient
        return NZBGetClient(
            host=record.host, port=record.port, username=record.username or "nzbget",
            password=record.password or "", use_ssl=record.use_ssl,
        )
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
    remove_from_client: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Remove an item from the queue.

    By default, only hides the item from Pressarr's queue (marks as
    processed). The torrent/download is NOT removed from the client.
    Pass remove_from_client=true to also delete from Deluge/qBittorrent.
    """
    from app.services.download_service import dismiss_download

    items = await _get_queue_items(db)
    item = next((i for i in items if i.id == item_id), None)

    if item and item.download_id:
        # Always mark as dismissed in Pressarr (hides from queue)
        dismiss_download(item.download_id)

        # Only remove from download client if explicitly requested
        if remove_from_client and item.download_client_id:
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

        if not item.download_client_id:
            # Direct download (AA/IA) — remove from tracker (cancels task)
            from app.services.direct_download_tracker import tracker as dd_tracker
            dd_tracker.remove(item.download_id)

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


@router.post("/{item_id}/import")
async def trigger_manual_import(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger import for a completed download."""
    from app.services.download_service import trigger_import

    items = await _get_queue_items(db)
    item = next((i for i in items if i.id == item_id), None)

    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Queue item not found")

    if not item.download_id:
        from fastapi import HTTPException
        raise HTTPException(400, "No download ID for this item")

    result = await trigger_import(
        db, item.download_id,
        issue_id=item.issue_id,
        magazine_id=item.magazine_id,
    )
    if result.get("success"):
        await db.commit()
    return result


@router.delete("/bulk")
async def bulk_remove_from_queue(
    body: QueueBulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Remove multiple items from the queue."""
    for item_id in body.ids:
        await remove_from_queue(item_id, blocklist=body.blocklist, db=db)
    return {}
