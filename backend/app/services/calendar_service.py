"""Calendar and forecast service."""
import logging
from datetime import date, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.issue import Issue
from app.models.magazine import Magazine

logger = logging.getLogger(__name__)


def _add_months(d: date, months: int) -> date:
    """Add *months* calendar months to a date, clamping to valid day."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    import calendar as _cal
    day = min(d.day, _cal.monthrange(year, month)[1])
    return date(year, month, day)


# Frequency to callable: each returns a new date given a starting date
FREQUENCY_DELTAS: dict[str, timedelta | int] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "biweekly": timedelta(weeks=2),
    "monthly": 1,       # months
    "bimonthly": 2,     # months
    "quarterly": 3,     # months
    "semiannual": 6,    # months
    "annual": 12,       # months
}


def _advance_date(d: date, frequency: str) -> date:
    """Advance a date by one period of the given frequency."""
    delta = FREQUENCY_DELTAS[frequency]
    if isinstance(delta, timedelta):
        return d + delta
    # delta is an int representing months
    return _add_months(d, delta)


async def get_calendar(
    db: AsyncSession,
    start: date,
    end: date,
    magazine_id: int | None = None,
    include_forecast: bool = True,
) -> list[dict]:
    """Get calendar entries (real issues + forecasts) within date range."""
    query = select(Issue).join(Magazine)

    filters = [
        Issue.publication_date >= start,
        Issue.publication_date <= end,
    ]

    if magazine_id is not None:
        filters.append(Issue.magazine_id == magazine_id)

    if not include_forecast:
        filters.append(Issue.is_forecast == False)  # noqa: E712

    query = query.where(and_(*filters)).order_by(Issue.publication_date)

    result = await db.execute(query)
    issues = result.scalars().all()

    entries = []
    for issue in issues:
        # Load the magazine title
        mag_result = await db.execute(
            select(Magazine).where(Magazine.id == issue.magazine_id)
        )
        mag = mag_result.scalars().first()

        entries.append({
            "issue_id": issue.id if not issue.is_forecast else None,
            "magazine_id": issue.magazine_id,
            "magazine_title": mag.title if mag else "Unknown",
            "cover_url": f"/api/v1/issue/{issue.id}/cover" if issue.cover_path else None,
            "date": issue.publication_date,
            "number": issue.number,
            "status": issue.status,
            "is_forecast": issue.is_forecast,
        })
    return entries


async def generate_forecasts(
    db: AsyncSession,
    magazine: Magazine,
    months_ahead: int = 6,
) -> list[Issue]:
    """Generate forecast issues for a magazine based on its frequency."""
    if magazine.frequency == "irregular" or magazine.frequency not in FREQUENCY_DELTAS:
        return []

    # Parse excluded weekdays (ISO: 0=Monday … 6=Sunday)
    excluded: set[int] = set()
    if magazine.excluded_days:
        excluded = {int(d) for d in magazine.excluded_days.split(",") if d.strip()}

    today = date.today()
    end_date = _add_months(today, months_ahead)

    # Determine the earliest date we should generate forecasts for
    start_date = today
    monitoring_start = getattr(magazine, "monitoring_start_date", None)
    if monitoring_start:
        if isinstance(monitoring_start, str):
            monitoring_start = date.fromisoformat(monitoring_start)
        if monitoring_start > start_date:
            start_date = monitoring_start

    # Find the last known issue date
    result = await db.execute(
        select(Issue)
        .where(
            Issue.magazine_id == magazine.id,
            Issue.is_forecast == False,  # noqa: E712
        )
        .order_by(Issue.publication_date.desc().nullslast())
        .limit(1)
    )
    last_issue = result.scalars().first()

    if last_issue and last_issue.publication_date:
        next_date = _advance_date(last_issue.publication_date, magazine.frequency)
    else:
        # No known issues, start from today
        next_date = start_date

    # Find last known issue number
    last_number = None
    if last_issue and last_issue.number is not None:
        last_number = last_issue.number

    # Remove existing forecasts for this magazine — but KEEP forecasts that
    # have been promoted to "wanted" or grabbed ("snatched"), as those are
    # actively tracked for download.
    existing_forecasts = await db.execute(
        select(Issue).where(
            Issue.magazine_id == magazine.id,
            Issue.is_forecast == True,  # noqa: E712
            Issue.status.in_(["upcoming", "delayed", "skipped"]),
        )
    )
    for forecast in existing_forecasts.scalars().all():
        await db.delete(forecast)
    await db.flush()

    # Collect existing real issue numbers to avoid unique constraint violations
    existing_numbers_result = await db.execute(
        select(Issue.number).where(
            Issue.magazine_id == magazine.id,
            Issue.is_forecast == False,  # noqa: E712
            Issue.number.isnot(None),
        )
    )
    existing_numbers: set[int] = {row[0] for row in existing_numbers_result.all()}

    # Estimate the starting number accounting for date gaps
    if last_issue and last_number is not None and last_issue.publication_date:
        # Count how many periods fit between last issue and the first forecast date
        cursor = last_issue.publication_date
        periods_skipped = 0
        while _advance_date(cursor, magazine.frequency) < max(next_date, start_date):
            cursor = _advance_date(cursor, magazine.frequency)
            if cursor.weekday() not in excluded:
                periods_skipped += 1
        number = last_number + periods_skipped + 1
    elif last_number is not None:
        number = last_number + 1
    else:
        number = None

    # Generate new forecasts
    created = []

    while next_date <= end_date:
        if next_date >= start_date and next_date.weekday() not in excluded:
            # Skip numbers already taken by real issues
            if number is not None:
                while number in existing_numbers:
                    number += 1

            forecast = Issue(
                magazine_id=magazine.id,
                number=number,
                publication_date=next_date,
                year=next_date.year,
                month=next_date.month,
                day=next_date.day,
                status="upcoming",
                monitored=magazine.monitored,
                is_forecast=True,
            )
            db.add(forecast)
            created.append(forecast)

            if number is not None:
                number += 1

        next_date = _advance_date(next_date, magazine.frequency)

    await db.flush()
    return created


async def reconcile_forecast(
    db: AsyncSession,
    issue: Issue,
    window_days: int = 7,
) -> bool:
    """Replace a matching forecast when a real issue is imported."""
    if not issue.publication_date:
        return False

    window_start = issue.publication_date - timedelta(days=window_days)
    window_end = issue.publication_date + timedelta(days=window_days)

    result = await db.execute(
        select(Issue).where(
            Issue.magazine_id == issue.magazine_id,
            Issue.is_forecast == True,  # noqa: E712
            Issue.publication_date >= window_start,
            Issue.publication_date <= window_end,
        ).limit(1)
    )
    forecast = result.scalars().first()

    if forecast:
        await db.delete(forecast)
        await db.flush()
        return True
    return False


async def promote_due_forecasts(db: AsyncSession) -> int:
    """Promote forecast issues from 'upcoming' to 'wanted' when their
    publication_date has arrived (publication_date <= today).

    Only promotes forecasts that are monitored and still 'upcoming'.
    Does NOT touch 'skipped' or 'delayed' forecasts.
    """
    today = date.today()
    result = await db.execute(
        select(Issue).where(
            Issue.is_forecast == True,  # noqa: E712
            Issue.status == "upcoming",
            Issue.monitored == True,  # noqa: E712
            Issue.publication_date <= today,
        )
    )
    forecasts = result.scalars().all()
    count = 0
    for forecast in forecasts:
        forecast.status = "wanted"
        forecast.is_forecast = False
        count += 1
    if count:
        await db.flush()
        logger.info("Promoted %d due forecasts to wanted", count)
    return count


async def mark_delayed_forecasts(db: AsyncSession) -> int:
    """Mark forecasts that are more than 7 days past their date as delayed."""
    cutoff = date.today() - timedelta(days=7)
    result = await db.execute(
        select(Issue).where(
            Issue.is_forecast == True,  # noqa: E712
            Issue.publication_date < cutoff,
            Issue.status.in_(["upcoming", "wanted"]),
        )
    )
    forecasts = result.scalars().all()
    count = 0
    for forecast in forecasts:
        forecast.status = "delayed"
        count += 1
    if count:
        await db.flush()
    return count


async def skip_forecast(db: AsyncSession, issue_id: int) -> Issue | None:
    """Skip a forecast issue."""
    result = await db.execute(
        select(Issue).where(Issue.id == issue_id, Issue.is_forecast == True)  # noqa: E712
    )
    issue = result.scalars().first()
    if not issue:
        return None
    issue.status = "skipped"
    await db.flush()
    return issue


async def unskip_forecast(db: AsyncSession, issue_id: int) -> Issue | None:
    """Unskip a forecast issue."""
    result = await db.execute(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.is_forecast == True,  # noqa: E712
            Issue.status == "skipped",
        )
    )
    issue = result.scalars().first()
    if not issue:
        return None
    issue.status = "upcoming"
    await db.flush()
    return issue
