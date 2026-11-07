"""GitHub issue 1: magnet-only results (The Pirate Bay through Prowlarr) are grabbed.

Prowlarr returns them with an empty ``downloadUrl``: the magnet is in ``guid``
(and sometimes ``magnetUrl``) — that magnet is the link sent to the download client.
"""

import httpx
import pytest

from app.indexers.base import release_link
from app.indexers.prowlarr import ProwlarrClient

MAGNET = "magnet:?xt=urn:btih:BEC20F4BF89D1F0EE04BCEB3A54CD67B7A48A3FA&dn=Magazine"


def test_release_link_prefers_the_download_url_then_the_magnet():
    assert release_link("https://x/t.torrent", MAGNET) == "https://x/t.torrent"
    assert release_link("", MAGNET) == MAGNET
    assert release_link(None, MAGNET) == MAGNET
    assert release_link("", "abc-123") is None


@pytest.mark.asyncio
async def test_a_magnet_only_result_carries_its_magnet_as_download_url():
    client = ProwlarrClient(url="http://localhost:9696", api_key="k")
    results = [
        {"guid": MAGNET, "title": "A", "indexer": "The Pirate Bay", "protocol": "torrent", "downloadUrl": ""},
        {"guid": "tpb-2", "title": "B", "indexer": "The Pirate Bay", "protocol": "torrent", "magnetUrl": MAGNET},
    ]
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=results)))
    found = await client.search("Magazine")
    assert [r.download_url for r in found] == [MAGNET, MAGNET]


@pytest.mark.asyncio
async def test_a_manual_grab_without_download_url_sends_the_magnet(client, monkeypatch):
    sent = {}

    async def fake_grab(db, **kwargs):
        sent.update(kwargs)
        return {"issueId": 1, "downloadId": "bec20f4b", "message": "Sent to qBittorrent"}

    monkeypatch.setattr("app.services.download_service.grab_release", fake_grab)
    body = {"issueId": 1, "magazineId": 1, "title": "A", "protocol": "torrent", "guid": MAGNET, "downloadUrl": ""}
    resp = await client.post("/api/v1/search/grab", json=body)
    assert resp.status_code == 200, resp.text
    assert sent["download_url"] == MAGNET


@pytest.mark.asyncio
async def test_a_grab_with_neither_link_is_still_refused(client):
    body = {"issueId": 1, "title": "A", "protocol": "torrent", "guid": "abc-123", "downloadUrl": ""}
    resp = await client.post("/api/v1/search/grab", json=body)
    assert resp.status_code == 422
