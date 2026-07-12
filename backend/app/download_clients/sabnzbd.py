"""SABnzbd download client via REST API."""

import httpx

from app.download_clients.base import DownloadClientBase, DownloadStatus


class SABnzbdClient(DownloadClientBase):
    """Client for the SABnzbd REST API."""

    def __init__(
        self,
        host: str,
        port: int,
        api_key: str,
        use_ssl: bool = False,
    ):
        scheme = "https" if use_ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}/sabnzbd/api"
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _call(self, mode: str, extra_params: dict | None = None) -> dict:
        """Make a SABnzbd API call."""
        params = {
            "apikey": self.api_key,
            "output": "json",
            "mode": mode,
        }
        if extra_params:
            params.update(extra_params)
        resp = await self._client.get(self.base_url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"SABnzbd error: {data['error']}")
        return data

    async def add_torrent(self, url: str, category: str = "pressarr") -> str:
        """SABnzbd does not support torrents."""
        raise NotImplementedError("SABnzbd does not support torrent downloads")

    async def add_nzb(self, url: str, category: str = "pressarr") -> str:
        """Add an NZB by URL. Returns the NZO ID."""
        data = await self._call(
            "addurl", {"name": url, "cat": category}
        )
        nzo_ids = data.get("nzo_ids", [])
        if not nzo_ids:
            raise RuntimeError("Failed to add NZB to SABnzbd")
        return nzo_ids[0]

    async def get_status(self, download_id: str) -> DownloadStatus | None:
        """Get status of a specific download by NZO ID."""
        for slot in await self._get_queue_raw():
            if slot.get("nzo_id") == download_id:
                return self._parse_queue_slot(slot)

        for slot in await self._get_history_raw():
            if slot.get("nzo_id") == download_id:
                return self._parse_history_slot(slot)

        return None

    async def get_all(self, category: str = "pressarr") -> list[DownloadStatus]:
        """Get downloads filtered by category."""
        queue = await self._get_queue_raw()
        history = await self._get_history_raw()

        results: list[DownloadStatus] = []
        for slot in queue:
            if category and slot.get("cat", "") != category:
                continue
            results.append(self._parse_queue_slot(slot))
        for slot in history:
            if category and slot.get("category", "") != category:
                continue
            results.append(self._parse_history_slot(slot))
        return results

    async def remove(
        self, download_id: str, delete_data: bool = False
    ) -> bool:
        """Remove a download by NZO ID."""
        try:
            # Try removing from queue first
            await self._call(
                "queue",
                {"name": "delete", "value": download_id, "del_files": int(delete_data)},
            )
            return True
        except Exception:
            try:
                # Try removing from history
                await self._call(
                    "history",
                    {"name": "delete", "value": download_id, "del_files": int(delete_data)},
                )
                return True
            except Exception:
                return False

    async def test_connection(self) -> tuple[bool, str]:
        """Test connection by getting server version."""
        try:
            data = await self._call("version")
            version = data.get("version", "unknown")
            return True, f"Connected to SABnzbd {version}"
        except Exception as e:
            return False, str(e)

    async def _get_queue_raw(self) -> list[dict]:
        """Get active queue slots as raw dicts."""
        data = await self._call("queue")
        return data.get("queue", {}).get("slots", [])

    async def _get_history_raw(self) -> list[dict]:
        """Get history slots as raw dicts."""
        data = await self._call("history", {"limit": 50})
        return data.get("history", {}).get("slots", [])

    def _parse_queue_slot(self, data: dict) -> DownloadStatus:
        """Parse a SABnzbd queue slot into DownloadStatus."""
        status = data.get("status", "").lower()
        status_map = {
            "downloading": "downloading",
            "queued": "downloading",
            "paused": "paused",
            "grabbing": "downloading",
        }
        # Parse size (SABnzbd returns as string like "1.5 GB")
        mb = data.get("mb", 0)
        mb_left = data.get("mbleft", 0)
        try:
            total_mb = float(mb)
            left_mb = float(mb_left)
            progress = (total_mb - left_mb) / total_mb if total_mb > 0 else 0.0
            size = int(total_mb * 1024 * 1024)
        except (ValueError, TypeError):
            progress = 0.0
            size = 0

        # Parse speed
        try:
            speed = int(float(data.get("kbpersec", 0)) * 1024)
        except (ValueError, TypeError):
            speed = 0

        # Parse ETA (SABnzbd returns as string like "0:02:30")
        timeleft = data.get("timeleft", "0:00:00")
        eta = self._parse_timeleft(timeleft)

        return DownloadStatus(
            download_id=data.get("nzo_id", ""),
            name=data.get("filename", ""),
            status=status_map.get(status, "downloading"),
            progress=progress,
            size=size,
            speed=speed,
            eta=eta,
        )

    def _parse_history_slot(self, data: dict) -> DownloadStatus:
        """Parse a SABnzbd history slot into DownloadStatus."""
        sab_status = data.get("status", "").lower()
        if sab_status == "completed":
            status = "completed"
        elif sab_status == "failed":
            status = "failed"
        else:
            status = "completed"

        size = data.get("bytes", 0)

        return DownloadStatus(
            download_id=data.get("nzo_id", ""),
            name=data.get("name", ""),
            status=status,
            progress=1.0 if status == "completed" else 0.0,
            size=size,
            speed=0,
            eta=0,
            save_path=data.get("storage"),
        )

    @staticmethod
    def _parse_timeleft(timeleft: str) -> int:
        """Parse SABnzbd time string 'H:MM:SS' to seconds."""
        try:
            parts = timeleft.split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except (ValueError, IndexError):
            pass
        return 0

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
