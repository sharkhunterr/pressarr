"""History event endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import PaginatedResource
from app.schemas.history import HistoryResource
from app.services import history_service

router = APIRouter(prefix="/api/v1/history", tags=["History"])


@router.get("", response_model=PaginatedResource[HistoryResource])
async def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: str | None = None,
    magazine_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    events, total = await history_service.list_events(
        db, page=page, page_size=page_size,
        event_type=event_type, magazine_id=magazine_id,
    )
    return PaginatedResource(
        page=page,
        page_size=page_size,
        total_records=total,
        records=[HistoryResource.model_validate(e) for e in events],
    )
