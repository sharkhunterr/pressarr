"""Integration tests for Magazine API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def seed_data(test_engine):
    """Seed a root_folder and quality_profile in the test DB."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as AS
    from app.models.root_folder import RootFolder
    from app.models.quality_profile import QualityProfile, QualityProfileItem

    factory = async_sessionmaker(test_engine, class_=AS, expire_on_commit=False)
    async with factory() as session:
        # Create root folder (use /tmp which always exists)
        root_folder = RootFolder(path="/tmp", is_default=True)
        session.add(root_folder)
        await session.flush()

        # Create quality profile
        profile = QualityProfile(name="Default", cutoff="pdf_hq", is_default=True)
        session.add(profile)
        await session.flush()

        item = QualityProfileItem(
            quality_profile_id=profile.id,
            quality="pdf_hq",
            allowed=True,
            sort_order=0,
        )
        session.add(item)
        await session.commit()

        return {"root_folder_id": root_folder.id, "quality_profile_id": profile.id}


def _magazine_payload(seed, **overrides):
    """Helper to build a magazine create payload."""
    data = {
        "title": "Science Magazine",
        "rootFolderId": seed["root_folder_id"],
        "qualityProfileId": seed["quality_profile_id"],
        "frequency": "monthly",
        "monitored": True,
    }
    data.update(overrides)
    return data


class TestMagazineCrud:
    """CRUD operation tests for /api/v1/magazine."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient, seed_data):
        resp = await client.get("/api/v1/magazine")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_create_magazine(self, client: AsyncClient, seed_data):
        seed = seed_data
        payload = _magazine_payload(seed)
        resp = await client.post("/api/v1/magazine", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Science Magazine"
        assert body["titleSlug"] == "science-magazine"
        assert body["frequency"] == "monthly"
        assert body["monitored"] is True
        assert body["id"] > 0
        # statistics should be present
        assert "statistics" in body
        assert body["statistics"]["issueCount"] == 0

    @pytest.mark.asyncio
    async def test_get_magazine(self, client: AsyncClient, seed_data):
        seed = seed_data
        create_resp = await client.post(
            "/api/v1/magazine", json=_magazine_payload(seed, title="Get Test Mag")
        )
        mag_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/magazine/{mag_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Get Test Mag"

    @pytest.mark.asyncio
    async def test_get_magazine_not_found(self, client: AsyncClient, seed_data):
        resp = await client.get("/api/v1/magazine/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_magazine(self, client: AsyncClient, seed_data):
        seed = seed_data
        create_resp = await client.post(
            "/api/v1/magazine", json=_magazine_payload(seed, title="Update Me")
        )
        mag_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/magazine/{mag_id}",
            json={"monitored": False, "frequency": "weekly"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["monitored"] is False
        assert body["frequency"] == "weekly"

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient, seed_data):
        resp = await client.put(
            "/api/v1/magazine/99999",
            json={"monitored": False},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_magazine(self, client: AsyncClient, seed_data):
        seed = seed_data
        create_resp = await client.post(
            "/api/v1/magazine", json=_magazine_payload(seed, title="Delete Me")
        )
        mag_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/magazine/{mag_id}")
        assert resp.status_code == 204

        # Confirm it's gone
        resp = await client.get(f"/api/v1/magazine/{mag_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient, seed_data):
        resp = await client.delete("/api/v1/magazine/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_with_files_param(self, client: AsyncClient, seed_data):
        seed = seed_data
        create_resp = await client.post(
            "/api/v1/magazine",
            json=_magazine_payload(seed, title="Delete With Files"),
        )
        mag_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/magazine/{mag_id}", params={"deleteFiles": "true"}
        )
        assert resp.status_code == 204


class TestMagazineUniqueness:
    """Tests for title_slug uniqueness and 409 handling."""

    @pytest.mark.asyncio
    async def test_duplicate_title_returns_409(self, client: AsyncClient, seed_data):
        seed = seed_data
        payload = _magazine_payload(seed, title="Unique Title")

        resp1 = await client.post("/api/v1/magazine", json=payload)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/magazine", json=payload)
        assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_different_titles_same_slug_returns_409(
        self, client: AsyncClient, seed_data
    ):
        """Titles that normalize to the same slug should conflict."""
        seed = seed_data

        resp1 = await client.post(
            "/api/v1/magazine",
            json=_magazine_payload(seed, title="Hello World!"),
        )
        assert resp1.status_code == 201

        # Different casing / punctuation but same slug
        resp2 = await client.post(
            "/api/v1/magazine",
            json=_magazine_payload(seed, title="Hello  World"),
        )
        assert resp2.status_code == 409


class TestMagazineStatistics:
    """Tests for computed magazine statistics."""

    @pytest.mark.asyncio
    async def test_statistics_defaults(self, client: AsyncClient, seed_data):
        seed = seed_data
        create_resp = await client.post(
            "/api/v1/magazine",
            json=_magazine_payload(seed, title="Stats Mag"),
        )
        assert create_resp.status_code == 201
        body = create_resp.json()
        stats = body["statistics"]
        assert stats["issueCount"] == 0
        assert stats["availableCount"] == 0
        assert stats["missingCount"] == 0
        assert stats["percentComplete"] == 0.0

    @pytest.mark.asyncio
    async def test_statistics_with_issues(self, client: AsyncClient, seed_data, test_engine):
        """Create issues directly in DB and verify stats via API."""
        seed = seed_data
        create_resp = await client.post(
            "/api/v1/magazine",
            json=_magazine_payload(seed, title="Stats Issues Mag"),
        )
        mag_id = create_resp.json()["id"]

        # Insert issues directly
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as AS
        from app.models.issue import Issue

        factory = async_sessionmaker(test_engine, class_=AS, expire_on_commit=False)
        async with factory() as session:
            session.add(Issue(magazine_id=mag_id, number=1, status="available"))
            session.add(Issue(magazine_id=mag_id, number=2, status="available"))
            session.add(Issue(magazine_id=mag_id, number=3, status="missing"))
            await session.commit()

        resp = await client.get(f"/api/v1/magazine/{mag_id}")
        assert resp.status_code == 200
        stats = resp.json()["statistics"]
        assert stats["issueCount"] == 3
        assert stats["availableCount"] == 2
        assert stats["missingCount"] == 1
        assert stats["percentComplete"] == pytest.approx(66.7, abs=0.1)


class TestMagazineListFiltering:
    """Tests for list filtering and sorting."""

    @pytest.mark.asyncio
    async def test_filter_by_monitored(self, client: AsyncClient, seed_data):
        seed = seed_data
        await client.post(
            "/api/v1/magazine",
            json=_magazine_payload(seed, title="Monitored Mag", monitored=True),
        )
        await client.post(
            "/api/v1/magazine",
            json=_magazine_payload(seed, title="Unmonitored Mag", monitored=False),
        )

        resp = await client.get("/api/v1/magazine", params={"monitored": "true"})
        assert resp.status_code == 200
        titles = [m["title"] for m in resp.json()]
        assert "Monitored Mag" in titles
        assert "Unmonitored Mag" not in titles

        resp = await client.get("/api/v1/magazine", params={"monitored": "false"})
        titles = [m["title"] for m in resp.json()]
        assert "Unmonitored Mag" in titles
