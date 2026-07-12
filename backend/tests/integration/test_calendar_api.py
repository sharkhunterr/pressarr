"""Integration tests for Calendar API endpoints."""
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.issue import Issue
from app.models.magazine import Magazine
from app.models.quality_profile import QualityProfile
from app.models.root_folder import RootFolder


@pytest_asyncio.fixture
async def seed_data(test_engine):
    """Seed a magazine with real issues and forecasts for testing."""
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with factory() as session:
        root = RootFolder(path="/magazines")
        session.add(root)
        await session.flush()

        profile = QualityProfile(name="Default", cutoff="pdf_hq", is_default=True)
        session.add(profile)
        await session.flush()

        magazine = Magazine(
            title="Science Monthly",
            title_slug="science-monthly",
            frequency="monthly",
            monitored=True,
            root_folder_id=root.id,
            quality_profile_id=profile.id,
        )
        session.add(magazine)
        await session.flush()

        today = date.today()

        # Real issues in range
        real_issue_1 = Issue(
            magazine_id=magazine.id,
            number=100,
            publication_date=today - timedelta(days=5),
            year=today.year,
            month=today.month,
            status="available",
        )
        real_issue_2 = Issue(
            magazine_id=magazine.id,
            number=101,
            publication_date=today,
            year=today.year,
            month=today.month,
            status="wanted",
        )

        # Forecast issue in range
        forecast_1 = Issue(
            magazine_id=magazine.id,
            publication_date=today + timedelta(days=10),
            year=today.year,
            month=today.month,
            status="upcoming",
            monitored=True,
            is_forecast=True,
        )

        # Issue outside date range (far future)
        far_future = today + timedelta(days=365)
        outside_issue = Issue(
            magazine_id=magazine.id,
            number=200,
            publication_date=far_future,
            year=far_future.year,
            month=far_future.month,
            status="missing",
        )

        session.add_all([real_issue_1, real_issue_2, forecast_1, outside_issue])
        await session.flush()
        await session.commit()

        return {
            "magazine": magazine,
            "real_issues": [real_issue_1, real_issue_2],
            "forecast": forecast_1,
            "outside_issue": outside_issue,
            "today": today,
        }


class TestCalendarGet:
    """Tests for GET /api/v1/calendar."""

    @pytest.mark.asyncio
    async def test_date_range_returns_correct_issues(
        self, client: AsyncClient, seed_data
    ):
        today = seed_data["today"]
        start = (today - timedelta(days=10)).isoformat()
        end = (today + timedelta(days=15)).isoformat()

        resp = await client.get(
            "/api/v1/calendar",
            params={"start": start, "end": end},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 2 real issues + 1 forecast within range
        assert len(data) == 3
        # Should be ordered by date
        dates = [d["date"] for d in data]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_excludes_outside_range(self, client: AsyncClient, seed_data):
        today = seed_data["today"]
        start = (today - timedelta(days=10)).isoformat()
        end = (today + timedelta(days=15)).isoformat()

        resp = await client.get(
            "/api/v1/calendar",
            params={"start": start, "end": end},
        )
        data = resp.json()
        # The far-future issue should not be in results
        issue_ids = [d.get("issueId") for d in data if d.get("issueId")]
        outside_id = seed_data["outside_issue"].id
        assert outside_id not in issue_ids

    @pytest.mark.asyncio
    async def test_forecast_exclusion(self, client: AsyncClient, seed_data):
        today = seed_data["today"]
        start = (today - timedelta(days=10)).isoformat()
        end = (today + timedelta(days=15)).isoformat()

        resp = await client.get(
            "/api/v1/calendar",
            params={"start": start, "end": end, "includeForecast": "false"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only real issues, no forecasts
        assert len(data) == 2
        assert all(d["isForecast"] is False for d in data)

    @pytest.mark.asyncio
    async def test_forecast_inclusion(self, client: AsyncClient, seed_data):
        today = seed_data["today"]
        start = (today - timedelta(days=10)).isoformat()
        end = (today + timedelta(days=15)).isoformat()

        resp = await client.get(
            "/api/v1/calendar",
            params={"start": start, "end": end, "includeForecast": "true"},
        )
        assert resp.status_code == 200
        data = resp.json()
        forecasts = [d for d in data if d["isForecast"] is True]
        assert len(forecasts) == 1

    @pytest.mark.asyncio
    async def test_default_date_range(self, client: AsyncClient, seed_data):
        """When no start/end is provided, defaults should work."""
        resp = await client.get("/api/v1/calendar")
        assert resp.status_code == 200
        # Should return a list (possibly empty or with data depending on month)
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_filter_by_magazine_id(self, client: AsyncClient, seed_data):
        today = seed_data["today"]
        mag_id = seed_data["magazine"].id
        start = (today - timedelta(days=10)).isoformat()
        end = (today + timedelta(days=15)).isoformat()

        resp = await client.get(
            "/api/v1/calendar",
            params={"start": start, "end": end, "magazineId": str(mag_id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["magazineId"] == mag_id for d in data)

    @pytest.mark.asyncio
    async def test_filter_by_nonexistent_magazine(self, client: AsyncClient, seed_data):
        today = seed_data["today"]
        start = (today - timedelta(days=10)).isoformat()
        end = (today + timedelta(days=15)).isoformat()

        resp = await client.get(
            "/api/v1/calendar",
            params={"start": start, "end": end, "magazineId": "99999"},
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestCalendarSkip:
    """Tests for POST /api/v1/calendar/{issue_id}/skip."""

    @pytest.mark.asyncio
    async def test_skip_forecast(self, client: AsyncClient, seed_data):
        forecast_id = seed_data["forecast"].id
        resp = await client.post(f"/api/v1/calendar/{forecast_id}/skip")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"
        assert data["isForecast"] is True

    @pytest.mark.asyncio
    async def test_skip_real_issue_returns_404(self, client: AsyncClient, seed_data):
        real_id = seed_data["real_issues"][0].id
        resp = await client.post(f"/api/v1/calendar/{real_id}/skip")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_skip_nonexistent_returns_404(self, client: AsyncClient, seed_data):
        resp = await client.post("/api/v1/calendar/99999/skip")
        assert resp.status_code == 404


class TestCalendarUnskip:
    """Tests for POST /api/v1/calendar/{issue_id}/unskip."""

    @pytest.mark.asyncio
    async def test_unskip_skipped_forecast(self, client: AsyncClient, seed_data, test_engine):
        """Skip then unskip a forecast."""
        forecast_id = seed_data["forecast"].id

        # First skip it
        skip_resp = await client.post(f"/api/v1/calendar/{forecast_id}/skip")
        assert skip_resp.status_code == 200
        assert skip_resp.json()["status"] == "skipped"

        # Then unskip it
        unskip_resp = await client.post(f"/api/v1/calendar/{forecast_id}/unskip")
        assert unskip_resp.status_code == 200
        data = unskip_resp.json()
        assert data["status"] == "upcoming"
        assert data["isForecast"] is True

    @pytest.mark.asyncio
    async def test_unskip_non_skipped_returns_404(self, client: AsyncClient, seed_data):
        """Unskipping a forecast that isn't skipped returns 404."""
        forecast_id = seed_data["forecast"].id
        resp = await client.post(f"/api/v1/calendar/{forecast_id}/unskip")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unskip_nonexistent_returns_404(self, client: AsyncClient, seed_data):
        resp = await client.post("/api/v1/calendar/99999/unskip")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unskip_real_issue_returns_404(self, client: AsyncClient, seed_data):
        real_id = seed_data["real_issues"][0].id
        resp = await client.post(f"/api/v1/calendar/{real_id}/unskip")
        assert resp.status_code == 404
