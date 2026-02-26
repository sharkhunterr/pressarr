"""Blocklist management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import PaginatedResource
from app.schemas.history import BlocklistResource, BlocklistBulkDeleteRequest
from app.services import history_service

router = APIRouter(prefix="/api/v1/blocklist", tags=["Blocklist"])


@router.get("", response_model=PaginatedResource[BlocklistResource])
async def list_blocklist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    magazine_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    entries, total = await history_service.list_blocklist(
        db, page=page, page_size=page_size, magazine_id=magazine_id,
    )
    return PaginatedResource(
        page=page,
        page_size=page_size,
        total_records=total,
        records=[BlocklistResource.model_validate(e) for e in entries],
    )


@router.delete("/{blocklist_id}", status_code=204)
async def remove_blocklist_entry(
    blocklist_id: int,
    db: AsyncSession = Depends(get_db),
):
    removed = await history_service.remove_from_blocklist(db, blocklist_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Blocklist entry not found")


@router.delete("/bulk", status_code=204)
async def bulk_remove_blocklist(
    body: BlocklistBulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    await history_service.bulk_remove_from_blocklist(db, body.ids)
