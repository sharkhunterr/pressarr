"""Contract tests for download clients with mocked HTTPX responses."""

import json

import httpx
import pytest

from app.download_clients.deluge import DelugeClient
from app.download_clients.nzbget import NZBGetClient
from app.download_clients.qbittorrent import QBittorrentClient
from app.download_clients.sabnzbd import SABnzbdClient
from app.download_clients.transmission import TransmissionClient


# ---------------------------------------------------------------------------
# Deluge
# ---------------------------------------------------------------------------

class TestDelugeClient:
    """Contract tests for the Deluge JSON-RPC client."""

    @pytest.fixture
    def client(self) -> DelugeClient:
        return DelugeClient(host="localhost", port=8112, password="deluge")

    @pytest.mark.asyncio
    async def test_add_torrent(self, client: DelugeClient):
        request_log: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            request_log.append(body)
            method = body["method"]
            if method == "auth.check_session":
                return httpx.Response(200, json={"result": False, "error": None, "id": body["id"]})
            if method == "auth.login":
                return httpx.Response(200, json={"result": True, "error": None, "id": body["id"]})
            if method == "core.add_torrent_url":
                return httpx.Response(200, json={"result": "abc123hash", "error": None, "id": body["id"]})
            return httpx.Response(200, json={"result": None, "error": None, "id": body["id"]})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.add_torrent("magnet:?xt=urn:btih:abc123")
        assert result == "abc123hash"

    @pytest.mark.asyncio
    async def test_add_nzb_raises(self, client: DelugeClient):
        with pytest.raises(NotImplementedError):
            await client.add_nzb("http://example.com/file.nzb")

    @pytest.mark.asyncio
    async def test_get_status(self, client: DelugeClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            method = body["method"]
            if method == "auth.check_session":
                return httpx.Response(200, json={"result": True, "error": None, "id": body["id"]})
            if method == "core.get_torrent_status":
                return httpx.Response(200, json={
                    "result": {
                        "name": "Test Torrent",
                        "state": "Downloading",
                        "progress": 50.0,
                        "total_size": 1048576,
                        "download_payload_rate": 102400,
                        "eta": 300,
                        "save_path": "/downloads",
                    },
                    "error": None,
                    "id": body["id"],
                })
            return httpx.Response(200, json={"result": None, "error": None, "id": body["id"]})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        status = await client.get_status("abc123hash")

        assert status is not None
        assert status.name == "Test Torrent"
        assert status.status == "downloading"
        assert status.progress == 0.5
        assert status.size == 1048576
        assert status.speed == 102400
        assert status.eta == 300
        assert status.save_path == "/downloads"

    @pytest.mark.asyncio
    async def test_get_all(self, client: DelugeClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            method = body["method"]
            if method == "auth.check_session":
                return httpx.Response(200, json={"result": True, "error": None, "id": body["id"]})
            if method == "core.get_torrents_status":
                return httpx.Response(200, json={
                    "result": {
                        "hash1": {"name": "Torrent 1", "state": "Downloading", "progress": 25.0, "total_size": 1024, "download_payload_rate": 0, "eta": 0, "save_path": "/dl"},
                        "hash2": {"name": "Torrent 2", "state": "Seeding", "progress": 100.0, "total_size": 2048, "download_payload_rate": 0, "eta": 0, "save_path": "/dl"},
                    },
                    "error": None,
                    "id": body["id"],
                })
            return httpx.Response(200, json={"result": None, "error": None, "id": body["id"]})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        statuses = await client.get_all()

        assert len(statuses) == 2
        names = {s.name for s in statuses}
        assert "Torrent 1" in names
        assert "Torrent 2" in names

    @pytest.mark.asyncio
    async def test_remove(self, client: DelugeClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            method = body["method"]
            if method == "auth.check_session":
                return httpx.Response(200, json={"result": True, "error": None, "id": body["id"]})
            if method == "core.remove_torrent":
                return httpx.Response(200, json={"result": True, "error": None, "id": body["id"]})
            return httpx.Response(200, json={"result": None, "error": None, "id": body["id"]})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.remove("abc123hash", delete_data=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client: DelugeClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            method = body["method"]
            if method == "auth.check_session":
                return httpx.Response(200, json={"result": True, "error": None, "id": body["id"]})
            if method == "daemon.info":
                return httpx.Response(200, json={"result": "2.1.1", "error": None, "id": body["id"]})
            return httpx.Response(200, json={"result": None, "error": None, "id": body["id"]})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        is_valid, message = await client.test_connection()

        assert is_valid is True
        assert "2.1.1" in message

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client: DelugeClient):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        is_valid, message = await client.test_connection()

        assert is_valid is False
        assert "Connection refused" in message


# ---------------------------------------------------------------------------
# qBittorrent
# ---------------------------------------------------------------------------

class TestQBittorrentClient:
    """Contract tests for the qBittorrent REST API client."""

    @pytest.fixture
    def client(self) -> QBittorrentClient:
        return QBittorrentClient(host="localhost", port=8080, username="admin", password="admin")

    @pytest.mark.asyncio
    async def test_add_torrent(self, client: QBittorrentClient):
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/login" in str(request.url):
                return httpx.Response(200, text="Ok.")
            if "/torrents/add" in str(request.url):
                return httpx.Response(200, text="Ok.")
            return httpx.Response(404)

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.add_torrent("magnet:?xt=urn:btih:abc123")
        assert result == "magnet:?xt=urn:btih:abc123"

    @pytest.mark.asyncio
    async def test_add_nzb_raises(self, client: QBittorrentClient):
        with pytest.raises(NotImplementedError):
            await client.add_nzb("http://example.com/file.nzb")

    @pytest.mark.asyncio
    async def test_get_status(self, client: QBittorrentClient):
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/login" in str(request.url):
                return httpx.Response(200, text="Ok.")
            if "/torrents/info" in str(request.url):
                return httpx.Response(200, json=[{
                    "hash": "abc123",
                    "name": "Test Torrent",
                    "state": "downloading",
                    "progress": 0.75,
                    "total_size": 2097152,
                    "dlspeed": 51200,
                    "eta": 120,
                    "save_path": "/downloads",
                }])
            return httpx.Response(404)

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        status = await client.get_status("abc123")

        assert status is not None
        assert status.download_id == "abc123"
        assert status.name == "Test Torrent"
        assert status.status == "downloading"
        assert status.progress == 0.75
        assert status.size == 2097152
        assert status.speed == 51200

    @pytest.mark.asyncio
    async def test_get_all(self, client: QBittorrentClient):
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/login" in str(request.url):
                return httpx.Response(200, text="Ok.")
            if "/torrents/info" in str(request.url):
                return httpx.Response(200, json=[
                    {"hash": "h1", "name": "T1", "state": "downloading", "progress": 0.5, "total_size": 1024, "dlspeed": 0, "eta": 0},
                    {"hash": "h2", "name": "T2", "state": "uploading", "progress": 1.0, "total_size": 2048, "dlspeed": 0, "eta": 0},
                ])
            return httpx.Response(404)

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        statuses = await client.get_all()

        assert len(statuses) == 2
        assert statuses[0].status == "downloading"
        assert statuses[1].status == "completed"

    @pytest.mark.asyncio
    async def test_remove(self, client: QBittorrentClient):
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/login" in str(request.url):
                return httpx.Response(200, text="Ok.")
            if "/torrents/delete" in str(request.url):
                return httpx.Response(200)
            return httpx.Response(404)

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.remove("abc123", delete_data=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client: QBittorrentClient):
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/login" in str(request.url):
                return httpx.Response(200, text="Ok.")
            if "/app/version" in str(request.url):
                return httpx.Response(200, text="v4.6.3")
            return httpx.Response(404)

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        is_valid, message = await client.test_connection()

        assert is_valid is True
        assert "v4.6.3" in message

    @pytest.mark.asyncio
    async def test_login_failure(self, client: QBittorrentClient):
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/login" in str(request.url):
                return httpx.Response(200, text="Fails.")
            return httpx.Response(404)

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        with pytest.raises(RuntimeError, match="authentication failed"):
            await client.add_torrent("magnet:?xt=test")


# ---------------------------------------------------------------------------
# Transmission
# ---------------------------------------------------------------------------

class TestTransmissionClient:
    """Contract tests for the Transmission JSON-RPC client."""

    @pytest.fixture
    def client(self) -> TransmissionClient:
        return TransmissionClient(host="localhost", port=9091, username="user", password="pass")

    @pytest.mark.asyncio
    async def test_add_torrent(self, client: TransmissionClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if body["method"] == "torrent-add":
                return httpx.Response(200, json={
                    "result": "success",
                    "arguments": {"torrent-added": {"hashString": "abc123hash", "id": 1, "name": "Test"}},
                })
            return httpx.Response(200, json={"result": "success", "arguments": {}})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.add_torrent("magnet:?xt=urn:btih:abc123")
        assert result == "abc123hash"

    @pytest.mark.asyncio
    async def test_add_nzb_raises(self, client: TransmissionClient):
        with pytest.raises(NotImplementedError):
            await client.add_nzb("http://example.com/file.nzb")

    @pytest.mark.asyncio
    async def test_409_session_id_challenge(self, client: TransmissionClient):
        """Transmission returns 409 with session ID on first request."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    409,
                    headers={"X-Transmission-Session-Id": "test-session-id"},
                )
            # Second call should have the session ID
            assert request.headers.get("X-Transmission-Session-Id") == "test-session-id"
            return httpx.Response(200, json={
                "result": "success",
                "arguments": {"torrent-added": {"hashString": "abc123", "id": 1, "name": "Test"}},
            })

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.add_torrent("magnet:?xt=test")
        assert result == "abc123"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_get_status(self, client: TransmissionClient):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "result": "success",
                "arguments": {"torrents": [{
                    "hashString": "abc123",
                    "name": "Test Torrent",
                    "status": 4,  # TR_STATUS_DOWNLOAD
                    "percentDone": 0.65,
                    "totalSize": 5242880,
                    "rateDownload": 204800,
                    "eta": 60,
                    "downloadDir": "/downloads",
                    "errorString": "",
                }]},
            })

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        status = await client.get_status("abc123")

        assert status is not None
        assert status.download_id == "abc123"
        assert status.name == "Test Torrent"
        assert status.status == "downloading"
        assert status.progress == 0.65
        assert status.size == 5242880

    @pytest.mark.asyncio
    async def test_get_status_completed(self, client: TransmissionClient):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "result": "success",
                "arguments": {"torrents": [{
                    "hashString": "abc123",
                    "name": "Done Torrent",
                    "status": 6,  # TR_STATUS_SEED
                    "percentDone": 1.0,
                    "totalSize": 1024,
                    "rateDownload": 0,
                    "eta": -1,
                    "downloadDir": "/dl",
                    "errorString": "",
                }]},
            })

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        status = await client.get_status("abc123")

        assert status is not None
        assert status.status == "completed"
        assert status.progress == 1.0
        assert status.eta == 0  # -1 should be converted to 0

    @pytest.mark.asyncio
    async def test_remove(self, client: TransmissionClient):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"result": "success", "arguments": {}})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.remove("abc123", delete_data=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client: TransmissionClient):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "result": "success",
                "arguments": {"version": "4.0.5"},
            })

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        is_valid, message = await client.test_connection()

        assert is_valid is True
        assert "4.0.5" in message

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client: TransmissionClient):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        is_valid, message = await client.test_connection()

        assert is_valid is False
        assert "Connection refused" in message


# ---------------------------------------------------------------------------
# SABnzbd
# ---------------------------------------------------------------------------

class TestSABnzbdClient:
    """Contract tests for the SABnzbd REST API client."""

    @pytest.fixture
    def client(self) -> SABnzbdClient:
        return SABnzbdClient(host="localhost", port=8080, api_key="test-key")

    @pytest.mark.asyncio
    async def test_add_nzb(self, client: SABnzbdClient):
        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            assert "mode=addurl" in url_str
            assert "apikey=test-key" in url_str
            return httpx.Response(200, json={"status": True, "nzo_ids": ["SABnzbd_nzo_abc123"]})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.add_nzb("http://example.com/file.nzb", category="pressarr")
        assert result == "SABnzbd_nzo_abc123"

    @pytest.mark.asyncio
    async def test_add_torrent_raises(self, client: SABnzbdClient):
        with pytest.raises(NotImplementedError):
            await client.add_torrent("magnet:?xt=test")

    @pytest.mark.asyncio
    async def test_get_status_from_queue(self, client: SABnzbdClient):
        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "mode=queue" in url_str:
                return httpx.Response(200, json={
                    "queue": {"slots": [{
                        "nzo_id": "nzo_abc123",
                        "filename": "Test NZB",
                        "status": "Downloading",
                        "mb": "100",
                        "mbleft": "50",
                        "kbpersec": "1024",
                        "timeleft": "0:01:30",
                    }]},
                })
            if "mode=history" in url_str:
                return httpx.Response(200, json={"history": {"slots": []}})
            return httpx.Response(200, json={})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        status = await client.get_status("nzo_abc123")

        assert status is not None
        assert status.download_id == "nzo_abc123"
        assert status.name == "Test NZB"
        assert status.status == "downloading"
        assert status.progress == pytest.approx(0.5, abs=0.01)
        assert status.speed == 1024 * 1024  # 1024 KB/s

    @pytest.mark.asyncio
    async def test_get_status_from_history(self, client: SABnzbdClient):
        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "mode=queue" in url_str:
                return httpx.Response(200, json={"queue": {"slots": []}})
            if "mode=history" in url_str:
                return httpx.Response(200, json={
                    "history": {"slots": [{
                        "nzo_id": "nzo_done",
                        "name": "Completed NZB",
                        "status": "Completed",
                        "bytes": 104857600,
                        "storage": "/downloads/complete",
                    }]},
                })
            return httpx.Response(200, json={})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        status = await client.get_status("nzo_done")

        assert status is not None
        assert status.status == "completed"
        assert status.progress == 1.0
        assert status.save_path == "/downloads/complete"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client: SABnzbdClient):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"version": "4.2.1"})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        is_valid, message = await client.test_connection()

        assert is_valid is True
        assert "4.2.1" in message

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client: SABnzbdClient):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        is_valid, message = await client.test_connection()

        assert is_valid is False
        assert "Connection refused" in message

    @pytest.mark.asyncio
    async def test_parse_timeleft(self, client: SABnzbdClient):
        assert SABnzbdClient._parse_timeleft("1:30:45") == 5445
        assert SABnzbdClient._parse_timeleft("0:02:30") == 150
        assert SABnzbdClient._parse_timeleft("0:00:00") == 0
        assert SABnzbdClient._parse_timeleft("invalid") == 0

    @pytest.mark.asyncio
    async def test_remove(self, client: SABnzbdClient):
        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "mode=queue" in url_str:
                return httpx.Response(200, json={"status": True})
            return httpx.Response(200, json={})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.remove("nzo_abc123")
        assert result is True


# ---------------------------------------------------------------------------
# NZBGet
# ---------------------------------------------------------------------------

class TestNZBGetClient:
    """Contract tests for the NZBGet JSON-RPC client."""

    @pytest.fixture
    def client(self) -> NZBGetClient:
        return NZBGetClient(host="localhost", port=6789, username="nzbget", password="tegbzn6789")

    @pytest.mark.asyncio
    async def test_add_nzb(self, client: NZBGetClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if body["method"] == "append":
                return httpx.Response(200, json={"result": 42})
            return httpx.Response(200, json={"result": None})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.add_nzb("http://example.com/file.nzb", category="pressarr")
        assert result == "42"

    @pytest.mark.asyncio
    async def test_add_torrent_raises(self, client: NZBGetClient):
        with pytest.raises(NotImplementedError):
            await client.add_torrent("magnet:?xt=test")

    @pytest.mark.asyncio
    async def test_get_status_from_queue(self, client: NZBGetClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if body["method"] == "listgroups":
                return httpx.Response(200, json={"result": [{
                    "NZBID": 42,
                    "NZBName": "Test NZB",
                    "FileSizeMB": 100,
                    "RemainingSizeMB": 50,
                    "ActiveDownloads": 1,
                    "Category": "pressarr",
                    "DestDir": "/downloads",
                }]})
            if body["method"] == "history":
                return httpx.Response(200, json={"result": []})
            return httpx.Response(200, json={"result": None})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        status = await client.get_status("42")

        assert status is not None
        assert status.download_id == "42"
        assert status.name == "Test NZB"
        assert status.status == "downloading"
        assert status.progress == pytest.approx(0.5, abs=0.01)

    @pytest.mark.asyncio
    async def test_get_status_from_history(self, client: NZBGetClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if body["method"] == "listgroups":
                return httpx.Response(200, json={"result": []})
            if body["method"] == "history":
                return httpx.Response(200, json={"result": [{
                    "NZBID": 42,
                    "NZBName": "Completed NZB",
                    "FileSizeMB": 100,
                    "ParStatus": "SUCCESS",
                    "UnpackStatus": "SUCCESS",
                    "DeleteStatus": "",
                    "Category": "pressarr",
                    "DestDir": "/complete",
                }]})
            return httpx.Response(200, json={"result": None})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        status = await client.get_status("42")

        assert status is not None
        assert status.status == "completed"
        assert status.progress == 1.0
        assert status.save_path == "/complete"

    @pytest.mark.asyncio
    async def test_get_all_filtered_by_category(self, client: NZBGetClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if body["method"] == "listgroups":
                return httpx.Response(200, json={"result": [
                    {"NZBID": 1, "NZBName": "Match", "FileSizeMB": 50, "RemainingSizeMB": 25, "ActiveDownloads": 1, "Category": "pressarr", "DestDir": "/dl"},
                    {"NZBID": 2, "NZBName": "NoMatch", "FileSizeMB": 50, "RemainingSizeMB": 25, "ActiveDownloads": 1, "Category": "other", "DestDir": "/dl"},
                ]})
            if body["method"] == "history":
                return httpx.Response(200, json={"result": []})
            return httpx.Response(200, json={"result": None})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        statuses = await client.get_all(category="pressarr")

        assert len(statuses) == 1
        assert statuses[0].name == "Match"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client: NZBGetClient):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"result": "21.1"})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        is_valid, message = await client.test_connection()

        assert is_valid is True
        assert "21.1" in message

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client: NZBGetClient):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        is_valid, message = await client.test_connection()

        assert is_valid is False
        assert "Connection refused" in message

    @pytest.mark.asyncio
    async def test_remove(self, client: NZBGetClient):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if body["method"] == "editqueue":
                return httpx.Response(200, json={"result": True})
            return httpx.Response(200, json={"result": None})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        result = await client.remove("42")
        assert result is True
