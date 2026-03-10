"""Unit tests for calendar service."""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.issue import Issue
from app.models.magazine import Magazine
from app.models.quality_profile import QualityProfile
from app.models.root_folder import RootFolder
from app.services import calendar_service
from app.services.calendar_service import _add_months


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seed(test_session: AsyncSession):
    """Seed shared root folder and quality profile."""
    root = RootFolder(path="/magazines")
    test_session.add(root)
    await test_session.flush()

    profile = QualityProfile(name="Default", cutoff="pdf_hq", is_default=True)
    test_session.add(profile)
    await test_session.flush()

    return {"root_folder_id": root.id, "quality_profile_id": profile.id}


def _make_magazine(
    seed_data: dict,
    title: str = "Test Mag",
    frequency: str = "monthly",
) -> Magazine:
    return Magazine(
        title=title,
        title_slug=title.lower().replace(" ", "-"),
        frequency=frequency,
        monitored=True,
        root_folder_id=seed_data["root_folder_id"],
        quality_profile_id=seed_data["quality_profile_id"],
    )


# ---------------------------------------------------------------------------
# _add_months helper
# ---------------------------------------------------------------------------

class TestAddMonths:
    def test_add_one_month(self):
        assert _add_months(date(2025, 1, 15), 1) == date(2025, 2, 15)

    def test_add_months_year_rollover(self):
        assert _add_months(date(2025, 11, 15), 3) == date(2026, 2, 15)

    def test_add_months_clamp_day(self):
        # Jan 31 + 1 month -> Feb 28 (non-leap)
        assert _add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)


# ---------------------------------------------------------------------------
# Forecast generation — all 7 frequencies
# ---------------------------------------------------------------------------

class TestGenerateForecasts:
    """Test forecast generation for all supported frequencies."""

    @pytest.mark.asyncio
    async def test_weekly_forecasts(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Weekly Mag", frequency="weekly")
        test_session.add(mag)
        await test_session.flush()

        # Add a known issue 1 week ago
        today = date.today()
        last_date = today - timedelta(days=7)
        issue = Issue(
            magazine_id=mag.id, number=10,
            publication_date=last_date, year=last_date.year,
            month=last_date.month, status="available",
        )
        test_session.add(issue)
        await test_session.flush()

        created = await calendar_service.generate_forecasts(test_session, mag, months_ahead=1)
        assert len(created) > 0
        # All should be upcoming forecasts
        for fc in created:
            assert fc.is_forecast is True
            assert fc.status == "upcoming"
            assert fc.publication_date >= today
        # Numbers should be sequential starting from 11
        assert created[0].number == 11

    @pytest.mark.asyncio
    async def test_biweekly_forecasts(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Biweekly Mag", frequency="biweekly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        last_date = today - timedelta(days=14)
        issue = Issue(
            magazine_id=mag.id, number=5,
            publication_date=last_date, year=last_date.year,
            month=last_date.month, status="available",
        )
        test_session.add(issue)
        await test_session.flush()

        created = await calendar_service.generate_forecasts(test_session, mag, months_ahead=2)
        assert len(created) > 0
        # Every forecast should be ~14 days apart
        for i in range(1, len(created)):
            delta = (created[i].publication_date - created[i - 1].publication_date).days
            assert delta == 14

    @pytest.mark.asyncio
    async def test_monthly_forecasts(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Monthly Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        last_date = _add_months(today, -1)
        issue = Issue(
            magazine_id=mag.id, number=100,
            publication_date=last_date, year=last_date.year,
            month=last_date.month, status="available",
        )
        test_session.add(issue)
        await test_session.flush()

        created = await calendar_service.generate_forecasts(test_session, mag, months_ahead=6)
        assert len(created) >= 6
        assert created[0].number == 101

    @pytest.mark.asyncio
    async def test_bimonthly_forecasts(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Bimonthly Mag", frequency="bimonthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        last_date = _add_months(today, -2)
        issue = Issue(
            magazine_id=mag.id, number=20,
            publication_date=last_date, year=last_date.year,
            month=last_date.month, status="available",
        )
        test_session.add(issue)
        await test_session.flush()

        created = await calendar_service.generate_forecasts(test_session, mag, months_ahead=6)
        assert len(created) >= 3
        assert created[0].number == 21

    @pytest.mark.asyncio
    async def test_quarterly_forecasts(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Quarterly Mag", frequency="quarterly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        last_date = _add_months(today, -3)
        issue = Issue(
            magazine_id=mag.id, number=50,
            publication_date=last_date, year=last_date.year,
            month=last_date.month, status="available",
        )
        test_session.add(issue)
        await test_session.flush()

        created = await calendar_service.generate_forecasts(test_session, mag, months_ahead=12)
        assert len(created) >= 4
        assert created[0].number == 51

    @pytest.mark.asyncio
    async def test_semiannual_forecasts(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Semiannual Mag", frequency="semiannual")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        last_date = _add_months(today, -6)
        issue = Issue(
            magazine_id=mag.id, number=8,
            publication_date=last_date, year=last_date.year,
            month=last_date.month, status="available",
        )
        test_session.add(issue)
        await test_session.flush()

        created = await calendar_service.generate_forecasts(test_session, mag, months_ahead=12)
        assert len(created) >= 2
        assert created[0].number == 9

    @pytest.mark.asyncio
    async def test_annual_forecasts(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Annual Mag", frequency="annual")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        last_date = _add_months(today, -12)
        issue = Issue(
            magazine_id=mag.id, number=3,
            publication_date=last_date, year=last_date.year,
            month=last_date.month, status="available",
        )
        test_session.add(issue)
        await test_session.flush()

        created = await calendar_service.generate_forecasts(test_session, mag, months_ahead=24)
        assert len(created) >= 2
        assert created[0].number == 4

    @pytest.mark.asyncio
    async def test_irregular_produces_no_forecast(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Irregular Mag", frequency="irregular")
        test_session.add(mag)
        await test_session.flush()

        created = await calendar_service.generate_forecasts(test_session, mag, months_ahead=6)
        assert created == []

    @pytest.mark.asyncio
    async def test_no_existing_issues_starts_from_today(
        self, test_session: AsyncSession, seed
    ):
        mag = _make_magazine(seed, title="Empty Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        created = await calendar_service.generate_forecasts(test_session, mag, months_ahead=3)
        assert len(created) >= 3
        # First forecast should be today
        assert created[0].publication_date == today
        # Numbers should be None (no reference issue)
        assert created[0].number is None

    @pytest.mark.asyncio
    async def test_regenerate_clears_old_forecasts(
        self, test_session: AsyncSession, seed
    ):
        mag = _make_magazine(seed, title="Regen Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        # Generate forecasts twice
        first = await calendar_service.generate_forecasts(test_session, mag, months_ahead=3)
        assert len(first) >= 3
        second = await calendar_service.generate_forecasts(test_session, mag, months_ahead=3)
        assert len(second) >= 3

        # Only the second batch should exist (old ones deleted)
        from sqlalchemy import select
        result = await test_session.execute(
            select(Issue).where(
                Issue.magazine_id == mag.id,
                Issue.is_forecast == True,  # noqa: E712
            )
        )
        all_forecasts = result.scalars().all()
        assert len(all_forecasts) == len(second)


# ---------------------------------------------------------------------------
# Delayed marking
# ---------------------------------------------------------------------------

class TestMarkDelayedForecasts:
    @pytest.mark.asyncio
    async def test_marks_old_forecasts_as_delayed(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Delay Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        old_date = today - timedelta(days=10)  # > 7 days ago

        forecast = Issue(
            magazine_id=mag.id,
            publication_date=old_date,
            year=old_date.year,
            month=old_date.month,
            status="upcoming",
            is_forecast=True,
        )
        test_session.add(forecast)
        await test_session.flush()

        count = await calendar_service.mark_delayed_forecasts(test_session)
        assert count == 1
        assert forecast.status == "delayed"

    @pytest.mark.asyncio
    async def test_does_not_mark_recent_forecasts(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Recent Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        recent_date = today - timedelta(days=3)  # < 7 days ago

        forecast = Issue(
            magazine_id=mag.id,
            publication_date=recent_date,
            year=recent_date.year,
            month=recent_date.month,
            status="upcoming",
            is_forecast=True,
        )
        test_session.add(forecast)
        await test_session.flush()

        count = await calendar_service.mark_delayed_forecasts(test_session)
        assert count == 0
        assert forecast.status == "upcoming"

    @pytest.mark.asyncio
    async def test_does_not_remark_already_delayed(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Already Delayed Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        old_date = today - timedelta(days=10)

        forecast = Issue(
            magazine_id=mag.id,
            publication_date=old_date,
            year=old_date.year,
            month=old_date.month,
            status="delayed",
            is_forecast=True,
        )
        test_session.add(forecast)
        await test_session.flush()

        count = await calendar_service.mark_delayed_forecasts(test_session)
        assert count == 0


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

class TestReconcileForecast:
    @pytest.mark.asyncio
    async def test_reconcile_replaces_matching_forecast(
        self, test_session: AsyncSession, seed
    ):
        mag = _make_magazine(seed, title="Reconcile Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()

        # Create a forecast
        forecast = Issue(
            magazine_id=mag.id,
            publication_date=today + timedelta(days=2),
            year=today.year,
            month=today.month,
            status="upcoming",
            is_forecast=True,
        )
        test_session.add(forecast)
        await test_session.flush()
        forecast_id = forecast.id

        # Create a real issue within the +-7 day window
        real_issue = Issue(
            magazine_id=mag.id,
            number=42,
            publication_date=today,
            year=today.year,
            month=today.month,
            status="available",
        )
        test_session.add(real_issue)
        await test_session.flush()

        replaced = await calendar_service.reconcile_forecast(test_session, real_issue)
        assert replaced is True

        # Forecast should be deleted
        from sqlalchemy import select
        result = await test_session.execute(
            select(Issue).where(Issue.id == forecast_id)
        )
        assert result.scalars().first() is None

    @pytest.mark.asyncio
    async def test_reconcile_no_match_outside_window(
        self, test_session: AsyncSession, seed
    ):
        mag = _make_magazine(seed, title="No Match Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()

        # Forecast 40 days ahead — outside the 32-day monthly window
        forecast = Issue(
            magazine_id=mag.id,
            publication_date=today + timedelta(days=40),
            year=today.year,
            month=today.month,
            status="upcoming",
            is_forecast=True,
        )
        test_session.add(forecast)
        await test_session.flush()

        real_issue = Issue(
            magazine_id=mag.id,
            number=99,
            publication_date=today,
            year=today.year,
            month=today.month,
            status="available",
        )
        test_session.add(real_issue)
        await test_session.flush()

        replaced = await calendar_service.reconcile_forecast(test_session, real_issue)
        assert replaced is False

    @pytest.mark.asyncio
    async def test_reconcile_no_publication_date(
        self, test_session: AsyncSession, seed
    ):
        mag = _make_magazine(seed, title="NoDate Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        real_issue = Issue(
            magazine_id=mag.id,
            number=1,
            publication_date=None,
            status="available",
        )
        test_session.add(real_issue)
        await test_session.flush()

        replaced = await calendar_service.reconcile_forecast(test_session, real_issue)
        assert replaced is False


# ---------------------------------------------------------------------------
# Skip / Unskip
# ---------------------------------------------------------------------------

class TestSkipUnskip:
    @pytest.mark.asyncio
    async def test_skip_forecast(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Skip Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        forecast = Issue(
            magazine_id=mag.id,
            publication_date=today + timedelta(days=30),
            year=today.year,
            month=today.month,
            status="upcoming",
            is_forecast=True,
        )
        test_session.add(forecast)
        await test_session.flush()

        result = await calendar_service.skip_forecast(test_session, forecast.id)
        assert result is not None
        assert result.status == "skipped"

    @pytest.mark.asyncio
    async def test_skip_non_forecast_returns_none(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Skip Real Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        real_issue = Issue(
            magazine_id=mag.id,
            number=1,
            publication_date=date.today(),
            status="available",
            is_forecast=False,
        )
        test_session.add(real_issue)
        await test_session.flush()

        result = await calendar_service.skip_forecast(test_session, real_issue.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_unskip_forecast(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Unskip Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        forecast = Issue(
            magazine_id=mag.id,
            publication_date=today + timedelta(days=30),
            year=today.year,
            month=today.month,
            status="skipped",
            is_forecast=True,
        )
        test_session.add(forecast)
        await test_session.flush()

        result = await calendar_service.unskip_forecast(test_session, forecast.id)
        assert result is not None
        assert result.status == "upcoming"

    @pytest.mark.asyncio
    async def test_unskip_non_skipped_returns_none(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Unskip Upcoming Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        forecast = Issue(
            magazine_id=mag.id,
            publication_date=today + timedelta(days=30),
            year=today.year,
            month=today.month,
            status="upcoming",
            is_forecast=True,
        )
        test_session.add(forecast)
        await test_session.flush()

        result = await calendar_service.unskip_forecast(test_session, forecast.id)
        assert result is None


# ---------------------------------------------------------------------------
# get_calendar
# ---------------------------------------------------------------------------

class TestGetCalendar:
    @pytest.mark.asyncio
    async def test_get_calendar_date_range(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="Cal Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        # Issue inside range
        inside = Issue(
            magazine_id=mag.id, number=1,
            publication_date=today, year=today.year,
            month=today.month, status="available",
        )
        # Issue outside range
        outside_date = today + timedelta(days=60)
        outside = Issue(
            magazine_id=mag.id, number=2,
            publication_date=outside_date, year=outside_date.year,
            month=outside_date.month, status="missing",
        )
        test_session.add_all([inside, outside])
        await test_session.flush()

        start = today - timedelta(days=1)
        end = today + timedelta(days=1)
        entries = await calendar_service.get_calendar(test_session, start, end)
        assert len(entries) == 1
        assert entries[0]["magazine_title"] == "Cal Mag"
        assert entries[0]["date"] == today

    @pytest.mark.asyncio
    async def test_get_calendar_exclude_forecast(self, test_session: AsyncSession, seed):
        mag = _make_magazine(seed, title="NoForecast Mag", frequency="monthly")
        test_session.add(mag)
        await test_session.flush()

        today = date.today()
        real = Issue(
            magazine_id=mag.id, number=1,
            publication_date=today, year=today.year,
            month=today.month, status="available",
        )
        forecast = Issue(
            magazine_id=mag.id,
            publication_date=today + timedelta(days=1),
            year=today.year, month=today.month,
            status="upcoming", is_forecast=True,
        )
        test_session.add_all([real, forecast])
        await test_session.flush()

        start = today - timedelta(days=1)
        end = today + timedelta(days=5)

        # With forecasts
        entries_all = await calendar_service.get_calendar(
            test_session, start, end, include_forecast=True
        )
        assert len(entries_all) == 2

        # Without forecasts
        entries_real = await calendar_service.get_calendar(
            test_session, start, end, include_forecast=False
        )
        assert len(entries_real) == 1
        assert entries_real[0]["is_forecast"] is False

    @pytest.mark.asyncio
    async def test_get_calendar_filter_by_magazine(self, test_session: AsyncSession, seed):
        mag1 = _make_magazine(seed, title="Cal Mag 1", frequency="monthly")
        mag2 = _make_magazine(seed, title="Cal Mag 2", frequency="weekly")
        test_session.add_all([mag1, mag2])
        await test_session.flush()

        today = date.today()
        issue1 = Issue(
            magazine_id=mag1.id, number=1,
            publication_date=today, year=today.year,
            month=today.month, status="available",
        )
        issue2 = Issue(
            magazine_id=mag2.id, number=1,
            publication_date=today, year=today.year,
            month=today.month, status="available",
        )
        test_session.add_all([issue1, issue2])
        await test_session.flush()

        start = today - timedelta(days=1)
        end = today + timedelta(days=1)
        entries = await calendar_service.get_calendar(
            test_session, start, end, magazine_id=mag1.id
        )
        assert len(entries) == 1
        assert entries[0]["magazine_id"] == mag1.id
