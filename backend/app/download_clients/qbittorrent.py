"""qBittorrent download client via REST API v2."""

import httpx

from app.download_clients.base import DownloadClientBase, DownloadStatus


class QBittorrentClient(DownloadClientBase):
    """Client for the qBittorrent Web API v2."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str = "admin",
        password: str = "",
        use_ssl: bool = False,
    ):
        scheme = "https" if use_ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}"
        self.username = username
        self.password = password
        self._client = httpx.AsyncClient(timeout=30.0)
        self._authenticated = False

    async def _login(self) -> None:
        """Authenticate via /api/v2/auth/login."""
        if self._authenticated:
            return
        resp = await self._client.post(
            f"{self.base_url}/api/v2/auth/login",
            data={"username": self.username, "password": self.password},
        )
        resp.raise_for_status()
        if resp.text.strip().lower() != "ok.":
            raise RuntimeError("qBittorrent authentication failed")
        self._authenticated = True

    async def add_torrent(self, url: str, category: str = "pressarr") -> str:
        """Add a torrent by URL. Returns the URL as an identifier."""
        await self._login()
        resp = await self._client.post(
            f"{self.base_url}/api/v2/torrents/add",
            data={"urls": url, "category": category},
        )
        resp.raise_for_status()
        # qBittorrent does not return a torrent hash on add; return URL
        return url

    async def add_nzb(self, url: str, category: str = "pressarr") -> str:
        """qBittorrent does not support NZBs."""
        raise NotImplementedError("qBittorrent does not support NZB downloads")

    async def get_status(self, download_id: str) -> DownloadStatus | None:
        """Get status of a specific torrent by hash."""
        await self._login()
        resp = await self._client.get(
            f"{self.base_url}/api/v2/torrents/info",
            params={"hashes": download_id},
        )
        resp.raise_for_status()
        torrents = resp.json()
        if not torrents:
            return None
        return self._parse_torrent(torrents[0])

    async def get_all(self, category: str = "pressarr") -> list[DownloadStatus]:
        """Get all torrents, optionally filtered by category."""
        await self._login()
        resp = await self._client.get(
            f"{self.base_url}/api/v2/torrents/info",
            params={"category": category},
        )
        resp.raise_for_status()
        return [self._parse_torrent(t) for t in resp.json()]

    async def remove(
        self, download_id: str, delete_data: bool = False
    ) -> bool:
        """Remove a torrent by hash."""
        await self._login()
        resp = await self._client.post(
            f"{self.base_url}/api/v2/torrents/delete",
            data={
                "hashes": download_id,
                "deleteFiles": "true" if delete_data else "false",
            },
        )
        return resp.status_code == 200

    async def test_connection(self) -> tuple[bool, str]:
        """Test connection by logging in and retrieving the app version."""
        try:
            await self._login()
            resp = await self._client.get(
                f"{self.base_url}/api/v2/app/version"
            )
            resp.raise_for_status()
            version = resp.text.strip()
            return True, f"Connected to qBittorrent {version}"
        except Exception as e:
            return False, str(e)

    def _parse_torrent(self, data: dict) -> DownloadStatus:
        """Parse a qBittorrent torrent info dict into DownloadStatus."""
        state = data.get("state", "").lower()
        status_map = {
            "downloading": "downloading",
            "stalledDL": "downloading",
            "metaDL": "downloading",
            "forcedDL": "downloading",
            "uploading": "completed",
            "stalledUP": "completed",
            "forcedUP": "completed",
            "pausedDL": "paused",
            "pausedUP": "completed",
            "queuedDL": "downloading",
            "queuedUP": "completed",
            "error": "failed",
            "missingFiles": "failed",
        }
        return DownloadStatus(
            download_id=data.get("hash", ""),
            name=data.get("name", ""),
            status=status_map.get(state, "downloading"),
            progress=data.get("progress", 0.0),
            size=data.get("total_size", 0),
            speed=data.get("dlspeed", 0),
            eta=data.get("eta", 0) or 0,
            save_path=data.get("save_path"),
        )

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
