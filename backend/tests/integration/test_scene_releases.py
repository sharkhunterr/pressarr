"""Scene releases (Bookys, tm.org): what a scan keeps, and how a grab
behaves while JDownloader is not set up."""

import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.indexers.magazine_scene.base import (
    HosterLink,
    MagazineSceneIndexerBase,
    MagazineSceneRelease,
)
from app.services import auto_grab_service, magazine_release_service

from .test_magazine_api import _magazine_payload, seed_data  # noqa: F401


def scene_release(title, slug, published=None):
    return MagazineSceneRelease(
        source="bookys",
        source_url=f"https://bookys.test/journaux/{slug}",
        title=title,
        hoster_links=[HosterLink("nitroflare.com", f"https://nitroflare.com/view/{slug}")],
        published_at=published,
    )


class FakeBookys(MagazineSceneIndexerBase):
    name = "bookys"

    def __init__(self, releases):
        self.releases = releases
        self.queries: list[str] = []

    async def search(self, query):
        self.queries.append(query)
        return self.releases

    async def test_connection(self):
        return True, "ok"

    async def close(self):
        pass


@pytest_asyncio.fixture
async def bookys(monkeypatch):
    fake = FakeBookys(
        [
            scene_release("Le Monde Du Samedi 7 Novembre 2026", "1", "2026-11-07"),
            scene_release("Le Monde des Ados - 4 Novembre 2026", "2"),
            scene_release("Le français dans le monde - Novembre 2026", "3"),
        ]
    )
    monkeypatch.setattr(
        magazine_release_service, "build_enabled_indexers", lambda config: [fake]
    )
    return fake


async def add_le_monde(client, seed, **overrides):
    resp = await client.post(
        "/api/v1/magazine",
        json=_magazine_payload(
            seed, title="Le Monde", frequency="daily", searchForMissingIssues=False,
            **overrides,
        ),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_a_scan_keeps_only_the_releases_of_the_magazine(
    client: AsyncClient, seed_data, bookys
):
    mag = await add_le_monde(client, seed_data)
    resp = await client.post(f"/api/v1/magazine/{mag}/releases/scan?source=bookys")

    assert resp.status_code == 200
    assert [(r["title"], r["publishedAt"]) for r in resp.json()] == [
        ("Le Monde Du Samedi 7 Novembre 2026", "2026-11-07")
    ]


@pytest.mark.asyncio
async def test_a_rescan_fills_in_the_release_date(client: AsyncClient, seed_data, bookys):
    bookys.releases = [scene_release("Le Monde Du Samedi 7 Novembre 2026", "1")]
    mag = await add_le_monde(client, seed_data)
    await client.post(f"/api/v1/magazine/{mag}/releases/scan")
    bookys.releases = [scene_release("Le Monde Du Samedi 7 Novembre 2026", "1", "2026-11-07")]
    resp = await client.post(f"/api/v1/magazine/{mag}/releases/scan")

    assert [r["publishedAt"] for r in resp.json()] == ["2026-11-07"]


@pytest.mark.asyncio
async def test_a_grab_while_jdownloader_is_off_leaves_the_release_grabbable(
    client: AsyncClient, seed_data, bookys, test_config
):
    test_config.jdownloader_enabled = False
    mag = await add_le_monde(client, seed_data)
    (release,) = (await client.post(f"/api/v1/magazine/{mag}/releases/scan")).json()

    resp = await client.post(f"/api/v1/magazine/{mag}/releases/{release['id']}/grab")

    assert resp.status_code == 409
    assert "disabled" in resp.json()["detail"]
    (after,) = (await client.get(f"/api/v1/magazine/{mag}/releases")).json()
    assert (after["status"], after["statusMessage"]) == ("available", None)


@pytest.mark.asyncio
async def test_adding_a_magazine_scans_nothing_while_jdownloader_is_off(
    client: AsyncClient, seed_data, bookys, test_config
):
    test_config.jdownloader_enabled = False
    mag = await add_le_monde(client, seed_data)

    assert bookys.queries == []
    assert (await client.get(f"/api/v1/magazine/{mag}/releases")).json() == []


@pytest.mark.asyncio
async def test_adding_a_magazine_grabs_its_back_catalogue_in_the_background(
    client: AsyncClient, seed_data, bookys, test_config, tmp_path
):
    test_config.jdownloader_enabled = True
    test_config.jdownloader_folderwatch = str(tmp_path / "folderwatch")
    test_config.jdownloader_output_path = str(tmp_path / "complete")
    mag = await add_le_monde(client, seed_data)
    await asyncio.gather(*auto_grab_service._background)

    assert bookys.queries
    (release,) = (await client.get(f"/api/v1/magazine/{mag}/releases")).json()
    assert release["status"] == "grabbed"
    assert len(list((tmp_path / "folderwatch").glob("*.crawljob"))) == 1
