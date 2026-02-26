"""Internet Archive download client for streaming files from archive.org."""

import asyncio
import logging
import time
from pathlib import Path

import httpx

from app.download_clients.base import DownloadClientBase, DownloadStatus

logger = logging.getLogger(__name__)

# Rate-limit: 1 request per second
_IA_SEMAPHORE = asyncio.Semaphore(1)
_IA_LAST_REQUEST: float = 0.0


async def _rate_limit() -> None:
    """Enforce 1 req/sec rate limit for archive.org."""
    global _IA_LAST_REQUEST
    async with _IA_SEMAPHORE:
        now = time.monotonic()
        elapsed = now - _IA_LAST_REQUEST
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        _IA_LAST_REQUEST = time.monotonic()


class InternetArchiveClient(DownloadClientBase):
    """Client for downloading files from the Internet Archive (archive.org).

    This is not a torrent/usenet client -- it streams files directly.
    ``add_torrent`` and ``add_nzb`` raise ``NotImplementedError``.
    """

    BASE_URL = "https://archive.org"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)
        # In-memory tracking of downloads (identifier -> DownloadStatus)
        self._downloads: dict[str, DownloadStatus] = {}

    # ---- DownloadClientBase interface ------------------------------------

    async def add_torrent(self, url: str, category: str = "pressarr") -> str:
        """Not supported -- Internet Archive uses direct downloads."""
        raise NotImplementedError(
            "Internet Archive does not support torrent downloads"
        )

    async def add_nzb(self, url: str, category: str = "pressarr") -> str:
        """Not supported -- Internet Archive uses direct downloads."""
        raise NotImplementedError(
            "Internet Archive does not support NZB downloads"
        )

    async def get_status(self, download_id: str) -> DownloadStatus | None:
        """Return the status of a tracked download."""
        return self._downloads.get(download_id)

    async def get_all(self, category: str = "pressarr") -> list[DownloadStatus]:
        """Return all in-memory tracked downloads."""
        return list(self._downloads.values())

    async def remove(
        self, download_id: str, delete_data: bool = False
    ) -> bool:
        """Remove a tracked download from the in-memory store."""
        if download_id in self._downloads:
            if delete_data:
                status = self._downloads[download_id]
                if status.save_path:
                    path = Path(status.save_path)
                    if path.exists():
                        path.unlink()
            del self._downloads[download_id]
            return True
        return False

    async def test_connection(self) -> tuple[bool, str]:
        """Ping archive.org/metadata/test to verify connectivity."""
        try:
            await _rate_limit()
            resp = await self._client.get(
                f"{self.BASE_URL}/metadata/test"
            )
            resp.raise_for_status()
            return True, "Connected to Internet Archive"
        except Exception as e:
            return False, str(e)

    # ---- IA-specific methods ---------------------------------------------

    async def download(
        self, identifier: str, filename: str, dest_dir: str
    ) -> str:
        """Download a specific file from an Internet Archive item.

        Parameters
        ----------
        identifier:
            The IA item identifier (e.g. ``sim_science-et-vie_2025-01``).
        filename:
            The file within the item to download.
        dest_dir:
            Local directory where the file will be saved.

        Returns
        -------
        str
            The local path of the downloaded file.
        """
        download_id = f"{identifier}/{filename}"
        url = f"{self.BASE_URL}/download/{identifier}/{filename}"

        dest_path = Path(dest_dir)
        dest_path.mkdir(parents=True, exist_ok=True)
        local_file = dest_path / filename

        # Register as in-progress
        self._downloads[download_id] = DownloadStatus(
            download_id=download_id,
            name=filename,
            status="downloading",
            progress=0.0,
            size=0,
            speed=0,
            eta=0,
            save_path=None,
        )

        try:
            logger.info("[IA client] Starting download url=%s dest=%s", url, local_file)
            await _rate_limit()
            # Retry with exponential backoff on 429
            for attempt in range(3):
                resp_head = await self._client.head(url)
                logger.info("[IA client] HEAD status=%d", resp_head.status_code)
                if resp_head.status_code == 429:
                    backoff = 5 * (2 ** attempt)  # 5s, 10s, 20s
                    logger.warning("[IA client] Rate limited, backing off %ds", backoff)
                    await asyncio.sleep(backoff)
                    continue
                break
            logger.info("[IA client] Starting GET stream...")
            async with self._client.stream("GET", url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                logger.info("[IA client] Streaming %d bytes...", total)
                self._downloads[download_id].size = total

                downloaded = 0
                start_time = time.monotonic()

                with open(local_file, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)

                        elapsed = time.monotonic() - start_time
                        speed = int(downloaded / elapsed) if elapsed > 0 else 0
                        progress = (
                            downloaded / total if total > 0 else 0.0
                        )
                        remaining = total - downloaded
                        eta = int(remaining / speed) if speed > 0 else 0

                        self._downloads[download_id].progress = progress
                        self._downloads[download_id].speed = speed
                        self._downloads[download_id].eta = eta

            # Mark completed
            self._downloads[download_id].status = "completed"
            self._downloads[download_id].progress = 1.0
            self._downloads[download_id].save_path = str(local_file)
            self._downloads[download_id].speed = 0
            self._downloads[download_id].eta = 0

            logger.info("[IA client] Download completed: %s (%d bytes)", local_file, local_file.stat().st_size)
            return str(local_file)

        except Exception as e:
            self._downloads[download_id].status = "failed"
            logger.error("[IA client] Download FAILED for %s: %s", download_id, e, exc_info=True)
            raise

    async def search_metadata(self, identifier: str) -> dict:
        """Fetch metadata for an Internet Archive item.

        Returns the raw metadata dict from the ``/metadata/{identifier}`` endpoint.
        """
        await _rate_limit()
        resp = await self._client.get(
            f"{self.BASE_URL}/metadata/{identifier}"
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
