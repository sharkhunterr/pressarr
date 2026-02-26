"""History event endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.history import History
from app.models.issue import Issue
from app.models.magazine import Magazine
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
    # Build query with LEFT JOINs to get magazine title and issue number
    query = (
        select(
            History,
            Magazine.title.label("magazine_title"),
            Issue.number.label("issue_number"),
        )
        .outerjoin(Magazine, History.magazine_id == Magazine.id)
        .outerjoin(Issue, History.issue_id == Issue.id)
    )
    count_query = select(func.count(History.id))

    if event_type:
        query = query.where(History.event_type == event_type)
        count_query = count_query.where(History.event_type == event_type)
    if magazine_id:
        query = query.where(History.magazine_id == magazine_id)
        count_query = count_query.where(History.magazine_id == magazine_id)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(History.date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    records = []
    for row in rows:
        event = row[0]
        records.append(HistoryResource(
            id=event.id,
            event_type=event.event_type,
            date=event.date,
            magazine_id=event.magazine_id,
            magazine_title=row.magazine_title,
            issue_id=event.issue_id,
            issue_number=row.issue_number,
            details=event.details,
        ))

    return PaginatedResource(
        page=page,
        page_size=page_size,
        total_records=total,
        records=records,
    )
