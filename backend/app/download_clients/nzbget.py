"""NZBGet download client via JSON-RPC with HTTP Basic auth."""

import httpx

from app.download_clients.base import DownloadClientBase, DownloadStatus


class NZBGetClient(DownloadClientBase):
    """Client for the NZBGet JSON-RPC API."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str = "nzbget",
        password: str = "tegbzn6789",
        use_ssl: bool = False,
    ):
        scheme = "https" if use_ssl else "http"
        self.rpc_url = f"{scheme}://{host}:{port}/jsonrpc"
        self._client = httpx.AsyncClient(
            timeout=30.0,
            auth=httpx.BasicAuth(username, password),
        )

    async def _call(self, method: str, params: list | None = None) -> object:
        """Make a JSON-RPC call to NZBGet."""
        payload = {
            "method": method,
            "params": params or [],
        }
        resp = await self._client.post(self.rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data and data["error"]:
            raise RuntimeError(f"NZBGet RPC error: {data['error']}")
        return data.get("result")

    async def add_torrent(self, url: str, category: str = "pressarr") -> str:
        """NZBGet does not support torrents."""
        raise NotImplementedError("NZBGet does not support torrent downloads")

    async def add_nzb(self, url: str, category: str = "pressarr") -> str:
        """Add an NZB by URL. Returns the NZB ID."""
        # append(NZBFilename, NZBContent, Category, Priority, DupeKey,
        #        DupeScore, DupeMode, PPParameters)
        # For URL-based adds, we use empty content and the URL as filename
        result = await self._call(
            "append",
            [
                "",          # NZBFilename (auto-detected)
                url,         # NZBContent (URL is accepted here)
                category,    # Category
                0,           # Priority (normal)
                False,       # AddToTop
                False,       # AddPaused
                "",          # DupeKey
                0,           # DupeScore
                "score",     # DupeMode
                [{"*:URL": url}],  # PPParameters with URL
            ],
        )
        if not result or result <= 0:
            raise RuntimeError("Failed to add NZB to NZBGet")
        return str(result)

    async def get_status(self, download_id: str) -> DownloadStatus | None:
        """Get status of a specific download by NZB ID."""
        # Check active queue
        groups = await self._call("listgroups")
        if groups:
            for group in groups:
                if str(group.get("NZBID")) == download_id:
                    return self._parse_group(group)

        # Check history
        history = await self._call("history")
        if history:
            for item in history:
                if str(item.get("NZBID")) == download_id:
                    return self._parse_history(item)

        return None

    async def get_all(self, category: str = "pressarr") -> list[DownloadStatus]:
        """Get all downloads, optionally filtered by category."""
        results: list[DownloadStatus] = []

        groups = await self._call("listgroups")
        if groups:
            for group in groups:
                if not category or group.get("Category") == category:
                    results.append(self._parse_group(group))

        history = await self._call("history")
        if history:
            for item in history:
                if not category or item.get("Category") == category:
                    results.append(self._parse_history(item))

        return results

    async def remove(
        self, download_id: str, delete_data: bool = False
    ) -> bool:
        """Remove a download by NZB ID."""
        try:
            # Try removing from queue
            result = await self._call("editqueue", ["GroupDelete", "", [int(download_id)]])
            if result:
                return True
        except Exception:
            pass

        try:
            # Try removing from history
            result = await self._call("editqueue", ["HistoryDelete", "", [int(download_id)]])
            return bool(result)
        except Exception:
            return False

    async def test_connection(self) -> tuple[bool, str]:
        """Test connection by getting NZBGet version."""
        try:
            version = await self._call("version")
            return True, f"Connected to NZBGet {version}"
        except Exception as e:
            return False, str(e)

    def _parse_group(self, data: dict) -> DownloadStatus:
        """Parse an NZBGet queue group into DownloadStatus."""
        file_size = data.get("FileSizeMB", 0) * 1024 * 1024
        remaining = data.get("RemainingSizeMB", 0) * 1024 * 1024
        progress = (file_size - remaining) / file_size if file_size > 0 else 0.0

        paused = data.get("PausedSizeLo", 0) > 0 or data.get("ActiveDownloads", 0) == 0
        status = "paused" if paused else "downloading"

        # Speed from global status, not per-group
        speed = 0

        # ETA calculation
        eta = 0
        if speed > 0 and remaining > 0:
            eta = int(remaining / speed)

        return DownloadStatus(
            download_id=str(data.get("NZBID", "")),
            name=data.get("NZBName", ""),
            status=status,
            progress=progress,
            size=int(file_size),
            speed=speed,
            eta=eta,
            save_path=data.get("DestDir"),
        )

    def _parse_history(self, data: dict) -> DownloadStatus:
        """Parse an NZBGet history item into DownloadStatus."""
        par_status = data.get("ParStatus", "")
        unpack_status = data.get("UnpackStatus", "")
        delete_status = data.get("DeleteStatus", "")

        if delete_status:
            status = "failed"
        elif par_status == "SUCCESS" and unpack_status in ("SUCCESS", "NONE"):
            status = "completed"
        elif par_status == "FAILURE" or unpack_status == "FAILURE":
            status = "failed"
        else:
            status = "completed"

        size = data.get("FileSizeMB", 0) * 1024 * 1024

        return DownloadStatus(
            download_id=str(data.get("NZBID", "")),
            name=data.get("NZBName", ""),
            status=status,
            progress=1.0 if status == "completed" else 0.0,
            size=int(size),
            speed=0,
            eta=0,
            save_path=data.get("DestDir"),
        )

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
