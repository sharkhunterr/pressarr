"""Calendar API endpoints."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.calendar import CalendarResource
from app.services import calendar_service

router = APIRouter(prefix="/api/v1/calendar", tags=["Calendar"])


@router.get("", response_model=list[CalendarResource])
async def get_calendar(
    start: date | None = Query(None),
    end: date | None = Query(None),
    magazine_id: int | None = Query(None, alias="magazineId"),
    include_forecast: bool = Query(True, alias="includeForecast"),
    db: AsyncSession = Depends(get_db),
):
    """Get calendar entries within a date range."""
    if start is None:
        start = date.today().replace(day=1)
    if end is None:
        end = start + timedelta(days=31)

    entries = await calendar_service.get_calendar(
        db, start, end,
        magazine_id=magazine_id,
        include_forecast=include_forecast,
    )
    return entries


@router.post("/{issue_id}/skip", response_model=CalendarResource)
async def skip_forecast(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Skip a forecast issue."""
    issue = await calendar_service.skip_forecast(db, issue_id)
    if issue is None:
        raise HTTPException(404, "Forecast not found")
    # Build response
    from sqlalchemy import select

    from app.models.magazine import Magazine
    mag_result = await db.execute(select(Magazine).where(Magazine.id == issue.magazine_id))
    mag = mag_result.scalars().first()
    return CalendarResource(
        issue_id=None,
        magazine_id=issue.magazine_id,
        magazine_title=mag.title if mag else "Unknown",
        date=issue.publication_date,
        number=issue.number,
        status=issue.status,
        is_forecast=True,
    )


@router.post("/{issue_id}/unskip", response_model=CalendarResource)
async def unskip_forecast(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Unskip a forecast issue."""
    issue = await calendar_service.unskip_forecast(db, issue_id)
    if issue is None:
        raise HTTPException(404, "Forecast not found or not skipped")
    from sqlalchemy import select

    from app.models.magazine import Magazine
    mag_result = await db.execute(select(Magazine).where(Magazine.id == issue.magazine_id))
    mag = mag_result.scalars().first()
    return CalendarResource(
        issue_id=None,
        magazine_id=issue.magazine_id,
        magazine_title=mag.title if mag else "Unknown",
        date=issue.publication_date,
        number=issue.number,
        status=issue.status,
        is_forecast=True,
    )
