"""Deluge download client via JSON-RPC."""

import httpx

from app.download_clients.base import DownloadClientBase, DownloadStatus


class DelugeClient(DownloadClientBase):
    """Client for Deluge's JSON-RPC API."""

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        use_ssl: bool = False,
    ):
        scheme = "https" if use_ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}"
        self.password = password
        self._client = httpx.AsyncClient(timeout=30.0)
        self._request_id = 0

    async def _call(self, method: str, params: list | None = None) -> dict:
        """Make a JSON-RPC call to Deluge."""
        self._request_id += 1
        payload = {
            "method": method,
            "params": params or [],
            "id": self._request_id,
        }
        resp = await self._client.post(
            f"{self.base_url}/json", json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"Deluge RPC error: {data['error']}")
        return data.get("result")

    async def _ensure_auth(self) -> None:
        """Authenticate with Deluge if needed."""
        result = await self._call("auth.check_session")
        if not result:
            await self._call("auth.login", [self.password])

    async def add_torrent(self, url: str, category: str = "pressarr") -> str:
        """Add a torrent by URL. Returns the torrent hash."""
        await self._ensure_auth()
        options = {"move_completed_path": category}
        torrent_id = await self._call(
            "core.add_torrent_url", [url, options]
        )
        if not torrent_id:
            raise RuntimeError("Failed to add torrent to Deluge")
        return torrent_id

    async def add_nzb(self, url: str, category: str = "pressarr") -> str:
        """Deluge does not support NZBs."""
        raise NotImplementedError("Deluge does not support NZB downloads")

    async def get_status(self, download_id: str) -> DownloadStatus | None:
        """Get status of a specific torrent by hash."""
        await self._ensure_auth()
        fields = [
            "name", "state", "progress", "total_size",
            "download_payload_rate", "eta", "save_path",
        ]
        result = await self._call(
            "core.get_torrent_status", [download_id, fields]
        )
        if not result:
            return None
        return self._parse_status(download_id, result)

    async def get_all(self, category: str = "pressarr") -> list[DownloadStatus]:
        """Get status of all torrents."""
        await self._ensure_auth()
        fields = [
            "name", "state", "progress", "total_size",
            "download_payload_rate", "eta", "save_path",
        ]
        result = await self._call(
            "core.get_torrents_status", [{}, fields]
        )
        if not result:
            return []
        return [
            self._parse_status(tid, info) for tid, info in result.items()
        ]

    async def remove(
        self, download_id: str, delete_data: bool = False
    ) -> bool:
        """Remove a torrent from Deluge."""
        await self._ensure_auth()
        result = await self._call(
            "core.remove_torrent", [download_id, delete_data]
        )
        return bool(result)

    async def test_connection(self) -> tuple[bool, str]:
        """Test connection by authenticating and getting version."""
        try:
            await self._ensure_auth()
            version = await self._call("daemon.info")
            return True, f"Connected to Deluge {version}"
        except Exception as e:
            return False, str(e)

    def _parse_status(self, download_id: str, data: dict) -> DownloadStatus:
        """Parse Deluge torrent status into DownloadStatus."""
        state = data.get("state", "").lower()
        status_map = {
            "downloading": "downloading",
            "seeding": "completed",
            "paused": "paused",
            "error": "failed",
            "queued": "downloading",
            "checking": "downloading",
        }
        return DownloadStatus(
            download_id=download_id,
            name=data.get("name", ""),
            status=status_map.get(state, "downloading"),
            progress=data.get("progress", 0.0) / 100.0,
            size=data.get("total_size", 0),
            speed=data.get("download_payload_rate", 0),
            eta=data.get("eta", 0) or 0,
            save_path=data.get("save_path"),
        )

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
