"""Transmission download client via JSON-RPC."""

import httpx

from app.download_clients.base import DownloadClientBase, DownloadStatus


class TransmissionClient(DownloadClientBase):
    """Client for the Transmission RPC API."""

    # Status codes from Transmission RPC spec
    _STATUS_STOPPED = 0
    _STATUS_CHECK_WAIT = 1
    _STATUS_CHECK = 2
    _STATUS_DOWNLOAD_WAIT = 3
    _STATUS_DOWNLOAD = 4
    _STATUS_SEED_WAIT = 5
    _STATUS_SEED = 6

    def __init__(
        self,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool = False,
    ):
        scheme = "https" if use_ssl else "http"
        self.rpc_url = f"{scheme}://{host}:{port}/transmission/rpc"
        self.username = username
        self.password = password
        self._session_id: str | None = None
        auth = None
        if username and password:
            auth = httpx.BasicAuth(username, password)
        self._client = httpx.AsyncClient(timeout=30.0, auth=auth)

    async def _rpc(self, method: str, arguments: dict | None = None) -> dict:
        """Make an RPC call, handling the 409 session-id challenge."""
        payload = {"method": method}
        if arguments:
            payload["arguments"] = arguments

        headers = {}
        if self._session_id:
            headers["X-Transmission-Session-Id"] = self._session_id

        resp = await self._client.post(
            self.rpc_url, json=payload, headers=headers
        )

        # Handle 409 CSRF challenge
        if resp.status_code == 409:
            self._session_id = resp.headers.get("X-Transmission-Session-Id", "")
            headers["X-Transmission-Session-Id"] = self._session_id
            resp = await self._client.post(
                self.rpc_url, json=payload, headers=headers
            )

        resp.raise_for_status()
        data = resp.json()
        if data.get("result") != "success":
            raise RuntimeError(
                f"Transmission RPC error: {data.get('result', 'unknown')}"
            )
        return data.get("arguments", {})

    async def add_torrent(self, url: str, category: str = "pressarr") -> str:
        """Add a torrent by URL. Returns the torrent hash."""
        args = {"filename": url}
        result = await self._rpc("torrent-add", args)
        torrent = result.get("torrent-added") or result.get("torrent-duplicate")
        if not torrent:
            raise RuntimeError("Failed to add torrent to Transmission")
        return str(torrent.get("hashString", ""))

    async def add_nzb(self, url: str, category: str = "pressarr") -> str:
        """Transmission does not support NZBs."""
        raise NotImplementedError("Transmission does not support NZB downloads")

    async def get_status(self, download_id: str) -> DownloadStatus | None:
        """Get status of a specific torrent by hash."""
        fields = [
            "hashString", "name", "status", "percentDone",
            "totalSize", "rateDownload", "eta", "downloadDir",
            "errorString",
        ]
        result = await self._rpc(
            "torrent-get", {"ids": [download_id], "fields": fields}
        )
        torrents = result.get("torrents", [])
        if not torrents:
            return None
        return self._parse_torrent(torrents[0])

    async def get_all(self, category: str = "pressarr") -> list[DownloadStatus]:
        """Get all torrents."""
        fields = [
            "hashString", "name", "status", "percentDone",
            "totalSize", "rateDownload", "eta", "downloadDir",
            "errorString",
        ]
        result = await self._rpc("torrent-get", {"fields": fields})
        torrents = result.get("torrents", [])
        return [self._parse_torrent(t) for t in torrents]

    async def remove(
        self, download_id: str, delete_data: bool = False
    ) -> bool:
        """Remove a torrent by hash."""
        try:
            await self._rpc(
                "torrent-remove",
                {"ids": [download_id], "delete-local-data": delete_data},
            )
            return True
        except Exception:
            return False

    async def test_connection(self) -> tuple[bool, str]:
        """Test connection by requesting session info."""
        try:
            result = await self._rpc("session-get", {"fields": ["version"]})
            version = result.get("version", "unknown")
            return True, f"Connected to Transmission {version}"
        except Exception as e:
            return False, str(e)

    def _parse_torrent(self, data: dict) -> DownloadStatus:
        """Parse a Transmission torrent dict into DownloadStatus."""
        status_code = data.get("status", 0)
        error = data.get("errorString", "")

        if error:
            status = "failed"
        elif status_code == self._STATUS_STOPPED:
            status = "paused"
        elif status_code in (self._STATUS_SEED, self._STATUS_SEED_WAIT):
            status = "completed"
        else:
            status = "downloading"

        return DownloadStatus(
            download_id=data.get("hashString", ""),
            name=data.get("name", ""),
            status=status,
            progress=data.get("percentDone", 0.0),
            size=data.get("totalSize", 0),
            speed=data.get("rateDownload", 0),
            eta=data.get("eta", 0) if data.get("eta", -1) >= 0 else 0,
            save_path=data.get("downloadDir"),
        )

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
