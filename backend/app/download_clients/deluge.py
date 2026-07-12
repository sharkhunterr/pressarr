"""Deluge download client via JSON-RPC."""

import logging
import re

import httpx

logger = logging.getLogger(__name__)

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

    async def _ensure_label(self, label: str) -> None:
        """Ensure the Label plugin label exists (create if needed)."""
        try:
            await self._call("label.add", [label])
        except RuntimeError:
            # Label already exists — ignore
            pass

    async def add_torrent(self, url: str, category: str = "pressarr") -> str:
        """Add a torrent by URL and tag it with the given label."""
        await self._ensure_auth()
        options: dict = {}
        try:
            torrent_id = await self._call(
                "core.add_torrent_url", [url, options]
            )
        except RuntimeError as e:
            # Deluge returns AddTorrentError when the torrent is already in session.
            # Extract the hash and treat it as a successful add.
            match = re.search(r"already in session \(([0-9a-fA-F]+)\)", str(e))
            if match:
                torrent_id = match.group(1)
                logger.info("Torrent already in Deluge, reusing existing: %s", torrent_id)
            else:
                raise
        if not torrent_id:
            raise RuntimeError("Failed to add torrent to Deluge")

        # Tag with label (requires Label plugin enabled in Deluge)
        try:
            await self._ensure_label(category)
            await self._call("label.set_torrent", [torrent_id, category])
        except RuntimeError as e:
            logger.warning(
                "Could not set label '%s' on torrent %s: %s. "
                "Enable the Label plugin in Deluge for reliable monitoring.",
                category, torrent_id, e,
            )

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
        """Get torrents filtered by label (requires Label plugin)."""
        await self._ensure_auth()
        fields = [
            "name", "state", "progress", "total_size",
            "download_payload_rate", "eta", "save_path", "label",
        ]
        # Try filtering by label via the Label plugin
        try:
            result = await self._call(
                "core.get_torrents_status", [{"label": category}, fields]
            )
        except RuntimeError as e:
            logger.warning(
                "Label plugin filter failed ('%s'): %s. "
                "Grab-registry fallback will be used for monitoring.",
                category, e,
            )
            result = None

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
        """Test connection by authenticating with Deluge WebUI."""
        try:
            result = await self._call("auth.login", [self.password])
            if not result:
                return False, "Authentication failed (wrong password?)"
            # Try to check if connected to a daemon
            connected = await self._call("web.connected")
            if connected:
                return True, "Connected to Deluge"
            # Not connected to a daemon yet, but auth works
            return True, "Authenticated with Deluge WebUI (no daemon connected)"
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
