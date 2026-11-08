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
    async def test_delete_with_files_removes_folder_and_files(
        self, client: AsyncClient, seed_data, test_engine, tmp_path
    ):
        root_id = await _library_root(test_engine, tmp_path / "library")
        resp = await client.post(
            "/api/v1/magazine",
            json=_magazine_payload(seed_data, title="Le Monde", rootFolderId=root_id),
        )
        mag_id = resp.json()["id"]
        folder = tmp_path / "library" / "Le Monde"
        tracked = folder / "Le Monde - 1 (2026-08-25).pdf"
        recovered = folder / "_pressarr_recovery" / "Le Monde - 2 (2026-08-26).pdf"
        elsewhere = tmp_path / "old-layout" / "Le Monde - 3.pdf"
        for f in (tracked, recovered, elsewhere):
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"%PDF")
        await _track_files(test_engine, mag_id, tracked, recovered, elsewhere)

        resp = await client.delete(
            f"/api/v1/magazine/{mag_id}", params={"deleteFiles": "true"}
        )

        assert resp.status_code == 204
        assert not folder.exists()
        assert not elsewhere.exists()
        assert (tmp_path / "library").is_dir()

    @pytest.mark.asyncio
    async def test_delete_without_files_keeps_them(
        self, client: AsyncClient, seed_data, test_engine, tmp_path
    ):
        root_id = await _library_root(test_engine, tmp_path / "library")
        resp = await client.post(
            "/api/v1/magazine",
            json=_magazine_payload(seed_data, title="Keep Me", rootFolderId=root_id),
        )
        mag_id = resp.json()["id"]
        tracked = tmp_path / "library" / "Keep Me" / "Keep Me - 1.pdf"
        tracked.parent.mkdir(parents=True)
        tracked.write_bytes(b"%PDF")
        await _track_files(test_engine, mag_id, tracked)

        resp = await client.delete(f"/api/v1/magazine/{mag_id}")

        assert resp.status_code == 204
        assert tracked.exists()

    @pytest.mark.asyncio
    async def test_delete_with_files_keeps_a_shared_folder(
        self, client: AsyncClient, seed_data, test_engine, tmp_path
    ):
        """'Le:Monde' and 'LeMonde' both land in <root>/LeMonde."""
        root_id = await _library_root(test_engine, tmp_path / "library")
        ids = []
        for title in ("Le:Monde", "LeMonde"):
            resp = await client.post(
                "/api/v1/magazine",
                json=_magazine_payload(seed_data, title=title, rootFolderId=root_id),
            )
            ids.append(resp.json()["id"])
        folder = tmp_path / "library" / "LeMonde"
        mine, theirs = folder / "mine.pdf", folder / "theirs.pdf"
        folder.mkdir(parents=True)
        mine.write_bytes(b"%PDF")
        theirs.write_bytes(b"%PDF")
        await _track_files(test_engine, ids[0], mine)
        await _track_files(test_engine, ids[1], theirs)

        resp = await client.delete(
            f"/api/v1/magazine/{ids[0]}", params={"deleteFiles": "true"}
        )

        assert resp.status_code == 204
        assert not mine.exists()
        assert theirs.exists()


async def _library_root(test_engine, path) -> int:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.root_folder import RootFolder

    path.mkdir(parents=True, exist_ok=True)
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        root = RootFolder(path=str(path), is_default=False)
        session.add(root)
        await session.commit()
        return root.id


async def _track_files(test_engine, magazine_id: int, *paths) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.issue_file import IssueFile

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        for p in paths:
            session.add(
                IssueFile(
                    magazine_id=magazine_id,
                    path=str(p),
                    relative_path=p.name,
                    size=4,
                    format="pdf",
                    original_filename=p.name,
                )
            )
        await session.commit()


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


@pytest.mark.asyncio
async def test_the_cover_shown_by_the_add_search_is_kept(client: AsyncClient, seed_data, monkeypatch):
    import io

    from PIL import Image

    from app.services import magazine_service

    logo = io.BytesIO()
    Image.new("RGBA", (40, 20), (0, 0, 0, 0)).save(logo, "PNG")

    async def download_cover(url):
        assert url == "https://example.test/logo.png"
        return logo.getvalue()

    monkeypatch.setattr(magazine_service, "download_cover", download_cover)
    resp = await client.post(
        "/api/v1/magazine",
        json=_magazine_payload(seed_data, coverUrl="https://example.test/logo.png"),
    )

    cover = resp.json()["coverPath"]
    assert cover.endswith("science-magazine-custom.jpg")
    # The transparent background comes out white, not black.
    assert Image.open(cover).getpixel((0, 0)) == (255, 255, 255)
