"""Scene grabs followed through JDownloader's API, like torrents: progress,
next mirror when one fails, import once finished."""

import asyncio
import json
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient

import app.database as db_module
from app.models.magazine_release import MagazineRelease
from app.services import activity_service, jdownloader_tracker

from .test_magazine_api import _magazine_payload, seed_data  # noqa: F401


class FakeJD:
    """JDownloader's API: what its lists hold, what was removed."""

    grabber: list[dict] = []
    downloads: list[dict] = []
    removed: list[int] = []

    def __init__(self, base_url):
        pass

    async def close(self):
        pass

    async def linkgrabber_links(self):
        return FakeJD.grabber

    async def download_links(self):
        return FakeJD.downloads

    async def download_packages(self):
        return [{"uuid": 1, "saveTo": "/output"}]

    async def remove_download_links(self, ids):
        FakeJD.removed += ids

    async def remove_linkgrabber_links(self, ids):
        FakeJD.removed += ids


def link(release_id, **fields):
    return {
        "uuid": 10,
        "packageUUID": 1,
        "comment": f"pressarr:release={release_id}",
        "host": "nitroflare.com",
        "name": f"{release_id}-Le-Monde.pdf",
        **fields,
    }


@pytest_asyncio.fixture
async def jd(monkeypatch, test_config, tmp_path):
    FakeJD.grabber, FakeJD.downloads, FakeJD.removed = [], [], []
    jdownloader_tracker._seen.clear()
    monkeypatch.setattr(jdownloader_tracker, "JDownloaderApi", FakeJD)
    test_config.jdownloader_enabled = True
    test_config.jdownloader_api_url = "http://jd.test:3128"
    test_config.jdownloader_folderwatch = str(tmp_path / "folderwatch")
    test_config.jdownloader_output_path = str(tmp_path / "out")
    test_config.jdownloader_output_path_in_jd2 = "/output"
    return test_config


@pytest_asyncio.fixture
async def grabbed(client: AsyncClient, seed_data, jd):
    """A Le Monde release sent to JDownloader on nitroflare."""
    jd.jdownloader_enabled = False  # no scan when the magazine is added
    resp = await client.post(
        "/api/v1/magazine",
        json=_magazine_payload(seed_data, title="Le Monde", searchForMissingIssues=False),
    )
    jd.jdownloader_enabled = True
    async with db_module.async_session_factory() as db:
        release = MagazineRelease(
            magazine_id=resp.json()["id"],
            source="bookys",
            source_url="https://bookys.test/journaux/1",
            title="Le Monde Du Samedi 7 Novembre 2026",
            size_bytes=1000,
            hoster_links=json.dumps(
                [
                    {"hoster": "nitroflare.com", "url": "https://nitroflare.com/view/1"},
                    {"hoster": "fileroy.com", "url": "https://fileroy.com/1"},
                ]
            ),
            status="grabbed",
            grabbed_at=datetime.utcnow(),
            tried_hosters=json.dumps(["nitroflare.com"]),
        )
        db.add(release)
        await db.commit()
        return release.id


async def follow(config):
    async with db_module.async_session_factory() as db:
        await jdownloader_tracker.track_scene_downloads(db, config)
    await asyncio.gather(*jdownloader_tracker._background)


async def release_row(release_id):
    async with db_module.async_session_factory() as db:
        return await db.get(MagazineRelease, release_id)


async def download_activity(release_id):
    aid = await activity_service.find_by_external_id(
        "download", f"jd:{release_id}", live_only=False
    )
    return await activity_service.get(aid)


@pytest.mark.asyncio
async def test_the_download_progress_shows_in_activity(grabbed, jd):
    FakeJD.downloads = [
        link(grabbed, running=True, bytesLoaded=500, bytesTotal=1000, speed=102400,
             eta=5, status="Downloading")
    ]
    await follow(jd)

    activity = await download_activity(grabbed)
    assert (activity.status, activity.progress) == ("running", 50.0)
    assert activity.status_message == "nitroflare.com — Downloading — 100 KB/s · ETA 0m05s"


@pytest.mark.asyncio
async def test_a_mirror_that_needs_a_captcha_hands_over_to_the_next(grabbed, jd, tmp_path):
    FakeJD.downloads = [link(grabbed, skipped=True, status="Skipped - Captcha required")]
    await follow(jd)

    assert FakeJD.removed == [10]
    release = await release_row(grabbed)
    assert release.status == "grabbed"
    assert json.loads(release.tried_hosters) == ["nitroflare.com", "fileroy.com"]
    (crawljob,) = (tmp_path / "folderwatch").glob("*.crawljob")
    assert "text=https://fileroy.com/1" in crawljob.read_text()
    activity = await download_activity(grabbed)
    assert activity.status == "running"
    assert "essai de fileroy.com" in activity.status_message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stopped", ["File not found", "Try restarting this link (plugin outdated?)"]
)
async def test_a_mirror_jdownloader_stopped_on_hands_over_to_the_next(grabbed, jd, stopped):
    FakeJD.downloads = [link(grabbed, running=False, bytesLoaded=0, status=stopped)]
    await follow(jd)

    assert json.loads((await release_row(grabbed)).tried_hosters)[-1] == "fileroy.com"
    assert stopped in (await download_activity(grabbed)).status_message


@pytest.mark.asyncio
async def test_a_queued_or_waiting_link_is_left_alone(grabbed, jd):
    FakeJD.downloads = [link(grabbed, running=False, bytesLoaded=0, status="Wait 52s")]
    await follow(jd)

    assert json.loads((await release_row(grabbed)).tried_hosters) == ["nitroflare.com"]


@pytest.mark.asyncio
async def test_a_mirror_stuck_without_a_byte_hands_over_to_the_next(grabbed, jd):
    async with db_module.async_session_factory() as db:
        release = await db.get(MagazineRelease, grabbed)
        release.grabbed_at = datetime.utcnow() - timedelta(minutes=11)
        await db.commit()
    # JD2 loops on a captcha it cannot solve: waits, starts, waits again.
    FakeJD.downloads = [link(grabbed, running=True, bytesLoaded=0, status="Wait 52s")]
    await follow(jd)

    release = await release_row(grabbed)
    assert json.loads(release.tried_hosters) == ["nitroflare.com", "fileroy.com"]
    assert "rien reçu en 10 min" in (await download_activity(grabbed)).status_message


@pytest.mark.asyncio
async def test_an_offline_last_mirror_fails_the_release(grabbed, jd):
    async with db_module.async_session_factory() as db:
        release = await db.get(MagazineRelease, grabbed)
        release.tried_hosters = json.dumps(["nitroflare.com", "fileroy.com"])
        await db.commit()
    FakeJD.grabber = [link(grabbed, host="fileroy.com", availability="OFFLINE")]
    await follow(jd)

    release = await release_row(grabbed)
    assert release.status == "failed"
    assert release.status_message == "fileroy.com : fichier hors ligne — aucun autre miroir"
    assert (await download_activity(grabbed)).status == "failed"


@pytest.mark.asyncio
async def test_a_finished_download_is_imported_like_a_torrent(grabbed, jd, monkeypatch, tmp_path):
    imported = []

    async def process_downloaded_file(db, path, config, magazine_id=None, issue_id=None, **kw):
        imported.append((path, magazine_id, kw["source_type"], kw["source_release_title"]))
        return {"success": True, "issue_id": 1, "message": "Imported"}

    monkeypatch.setattr(
        "app.services.import_service.process_downloaded_file", process_downloaded_file
    )
    FakeJD.downloads = [link(grabbed, finished=True, bytesLoaded=1000, bytesTotal=1000)]
    await follow(jd)

    release = await release_row(grabbed)
    assert imported == [
        (tmp_path / "out" / f"{grabbed}-Le-Monde.pdf", release.magazine_id, "scene",
         "Le Monde Du Samedi 7 Novembre 2026")
    ]
    assert release.status == "imported"
    assert FakeJD.removed == [10]
    assert (await download_activity(grabbed)).status == "success"


@pytest.mark.asyncio
async def test_a_link_jdownloader_drops_hands_over_to_the_next(grabbed, jd):
    async with db_module.async_session_factory() as db:
        release = await db.get(MagazineRelease, grabbed)
        release.grabbed_at = datetime.utcnow() - timedelta(minutes=3)
        await db.commit()
    # The crawljob was taken, no link came out of it: no plugin for that hoster.
    await follow(jd)

    release = await release_row(grabbed)
    assert json.loads(release.tried_hosters) == ["nitroflare.com", "fileroy.com"]
    assert "non pris en charge" in (await download_activity(grabbed)).status_message


@pytest.mark.asyncio
async def test_a_link_removed_from_jdownloader_fails_the_release(grabbed, jd):
    FakeJD.downloads = [link(grabbed, running=True, bytesLoaded=10, status="Downloading")]
    await follow(jd)
    FakeJD.downloads = []
    await follow(jd)

    release = await release_row(grabbed)
    assert (release.status, release.status_message) == ("failed", "JDownloader n'a plus ce lien")


@pytest.mark.asyncio
async def test_a_restart_resumes_the_same_activity(grabbed, jd):
    FakeJD.downloads = [link(grabbed, running=True, bytesLoaded=10, status="Downloading")]
    await follow(jd)
    before = await download_activity(grabbed)
    await activity_service.mark_interrupted_at_boot()
    await follow(jd)

    after = await download_activity(grabbed)
    assert (after.id, after.status, after.completed_at) == (before.id, "running", None)
