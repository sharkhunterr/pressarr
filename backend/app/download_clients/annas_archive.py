"""Anna's Archive download client for streaming files via LibGen/mirror links.

Handles ISP DNS blocks by resolving via Cloudflare DoH,
and navigates LibGen's multi-step download flow (file.php -> ads.php -> get.php).
"""

import asyncio
import logging
import re
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from lxml import html as lxml_html

from app.download_clients.base import DownloadClientBase, DownloadStatus
from app.metadata.annas_archive import USER_AGENT, AnnasArchiveProvider

logger = logging.getLogger(__name__)

# Rate-limit: 1 request per second
_AA_SEMAPHORE = asyncio.Semaphore(1)
_AA_LAST_REQUEST: float = 0.0

# Cache for DoH-resolved IPs  {hostname: ip}
_DOH_CACHE: dict[str, str] = {}


async def _rate_limit() -> None:
    """Enforce 1 req/sec rate limit for AA downloads."""
    global _AA_LAST_REQUEST
    async with _AA_SEMAPHORE:
        now = time.monotonic()
        elapsed = now - _AA_LAST_REQUEST
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        _AA_LAST_REQUEST = time.monotonic()


async def _resolve_via_doh(hostname: str) -> str | None:
    """Resolve hostname via Cloudflare DNS-over-HTTPS to bypass ISP blocks."""
    if hostname in _DOH_CACHE:
        return _DOH_CACHE[hostname]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://1.1.1.1/dns-query",
                params={"name": hostname, "type": "A"},
                headers={"Accept": "application/dns-json"},
            )
            resp.raise_for_status()
            data = resp.json()
            for ans in data.get("Answer", []):
                if ans.get("type") == 1:  # A record
                    ip = ans["data"]
                    _DOH_CACHE[hostname] = ip
                    logger.info("[DoH] Resolved %s -> %s", hostname, ip)
                    return ip
    except Exception as e:
        logger.warning("[DoH] Failed to resolve %s: %s", hostname, e)
    return None


def _is_dns_blocked(hostname: str) -> bool:
    """Check if a hostname resolves to a loopback address (ISP DNS block)."""
    try:
        ip = socket.gethostbyname(hostname)
        return ip.startswith("127.") or ip == "0.0.0.0"
    except socket.gaierror:
        return True


async def _make_client(
    url: str,
    connect_timeout: float = 10.0,
    read_timeout: float = 120.0,
) -> tuple[httpx.AsyncClient, str]:
    """Create an httpx client for *url*, bypassing DNS blocks if needed.

    Returns (client, request_url) where request_url is the URL to use
    with the client (may be a path-only URL if using base_url bypass).
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if not _is_dns_blocked(hostname):
        return (
            httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=connect_timeout, read=read_timeout,
                    write=30.0, pool=10.0,
                ),
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ),
            url,
        )

    # DNS blocked — resolve via DoH
    ip = await _resolve_via_doh(hostname)
    if not ip:
        raise ConnectionError(
            f"DNS blocked for {hostname} and DoH resolution also failed"
        )

    logger.info("[DNS bypass] %s blocked, routing via %s", hostname, ip)
    base_url = f"{parsed.scheme}://{ip}"
    request_url = parsed.path
    if parsed.query:
        request_url += f"?{parsed.query}"

    client = httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(
            connect=connect_timeout, read=read_timeout,
            write=30.0, pool=10.0,
        ),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Host": hostname},
        verify=False,  # cert is for hostname, not IP
    )
    return client, request_url


class AnnasArchiveClient(DownloadClientBase):
    """Download files from Anna's Archive via LibGen mirrors.

    Handles the full chain:
      AA detail page → LibGen file.php → ads.php → get.php → file stream
    with DNS-block bypass when needed.
    """

    def __init__(self, mirror: str = "annas-archive.li") -> None:
        self.mirror = mirror
        self._provider = AnnasArchiveProvider(mirror=mirror)
        self._downloads: dict[str, DownloadStatus] = {}

    # ---- DownloadClientBase interface ------------------------------------

    async def add_torrent(self, url: str, category: str = "pressarr") -> str:
        raise NotImplementedError

    async def add_nzb(self, url: str, category: str = "pressarr") -> str:
        raise NotImplementedError

    async def get_status(self, download_id: str) -> DownloadStatus | None:
        return self._downloads.get(download_id)

    async def get_all(self, category: str = "pressarr") -> list[DownloadStatus]:
        return list(self._downloads.values())

    async def remove(self, download_id: str, delete_data: bool = False) -> bool:
        if download_id in self._downloads:
            if delete_data:
                status = self._downloads[download_id]
                if status.save_path:
                    p = Path(status.save_path)
                    if p.exists():
                        p.unlink()
            del self._downloads[download_id]
            return True
        return False

    async def test_connection(self) -> tuple[bool, str]:
        return await self._provider.test_connection()

    # ---- Main download entry point ---------------------------------------

    async def download(self, md5: str, dest_dir: str) -> str:
        """Download a file from Anna's Archive by MD5 hash."""
        download_id = f"aa:{md5}"
        self._downloads[download_id] = DownloadStatus(
            download_id=download_id,
            name=f"{md5}.pdf",
            status="downloading",
            progress=0.0, size=0, speed=0, eta=0, save_path=None,
        )

        try:
            # Get download links from the detail page
            logger.info("[AA] Fetching download links for md5=%s", md5)
            links = await self._provider.get_download_links(md5)
            logger.info("[AA] Found %d download links: %s", len(links), links)

            if not links:
                raise ValueError(
                    f"No download links found for md5={md5}. "
                    f"Visit https://{self.mirror}/md5/{md5} manually."
                )

            # Try each link until one works
            last_error: Exception | None = None
            for i, link in enumerate(links):
                try:
                    logger.info("[AA] Trying link %d/%d: %s", i + 1, len(links), link)
                    path = await self._download_from_link(
                        download_id, link, md5, dest_dir
                    )
                    logger.info("[AA] SUCCESS via link %d: %s", i + 1, path)
                    return path
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "[AA] Link %d failed: %s", i + 1, e,
                    )
                    continue

            raise last_error or ValueError("All download links failed")

        except Exception as e:
            self._downloads[download_id].status = "failed"
            logger.error("[AA] Download failed for md5=%s: %s", md5, e, exc_info=True)
            raise

    # ---- Link resolution chain -------------------------------------------

    async def _download_from_link(
        self, download_id: str, url: str, md5: str, dest_dir: str,
    ) -> str:
        """Resolve a link (possibly multi-step) and stream the file."""
        await _rate_limit()

        # Determine what kind of link this is and resolve to a direct URL
        final_url = await self._resolve_to_direct_url(url, md5)

        logger.info("[AA] Final download URL: %s", final_url)
        return await self._stream_file(download_id, final_url, md5, dest_dir)

    async def _resolve_to_direct_url(self, url: str, md5: str) -> str:
        """Walk through intermediate pages to find the actual file URL.

        Handles:
        - libgen.li/file.php?id=X  →  ads.php?md5=X  →  get.php?md5=X&key=Y
        - library.lol / library.gift  →  cloudflare/IPFS link
        - direct file URLs (returned as-is)
        """
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        path_lower = parsed.path.lower()

        # LibGen file.php page → need to go through ads.php → get.php
        if "libgen" in hostname and "file.php" in path_lower:
            return await self._resolve_libgen_chain(url, md5)

        # LibGen ads.php page → extract get.php link
        if "libgen" in hostname and "ads.php" in path_lower:
            return await self._resolve_libgen_ads(url)

        # LibGen get.php → this is the direct download
        if "libgen" in hostname and "get.php" in path_lower:
            return url

        # library.lol / library.gift intermediate page
        if "library.lol" in hostname or "library.gift" in hostname:
            return await self._resolve_library_page(url)

        # Anything else — assume it's a direct URL
        return url

    async def _resolve_libgen_chain(self, file_php_url: str, md5: str) -> str:
        """LibGen file.php → ads.php → get.php with DNS bypass."""
        parsed = urlparse(file_php_url)
        base = f"{parsed.scheme}://{parsed.hostname}"

        # Build ads.php URL
        ads_url = f"{base}/ads.php?md5={md5}"
        logger.info("[AA libgen] file.php -> trying ads.php: %s", ads_url)
        return await self._resolve_libgen_ads(ads_url)

    async def _resolve_libgen_ads(self, ads_url: str) -> str:
        """Parse ads.php page to find get.php?md5=...&key=... link."""
        client, request_url = await _make_client(ads_url, connect_timeout=10.0, read_timeout=15.0)
        try:
            await _rate_limit()
            resp = await client.get(request_url)
            resp.raise_for_status()
        finally:
            await client.aclose()

        tree = lxml_html.fromstring(resp.text)
        # Look for get.php link with a key parameter
        all_links = tree.xpath("//a/@href")
        for href in all_links:
            href = str(href).strip()
            if "get.php" in href and "key=" in href:
                # Make absolute if relative
                if href.startswith("/") or href.startswith("get.php"):
                    parsed = urlparse(ads_url)
                    href = f"{parsed.scheme}://{parsed.hostname}/{href.lstrip('/')}"
                logger.info("[AA libgen] Found get.php link: %s", href)
                return href

        raise ValueError(f"No get.php download link found on {ads_url}")

    async def _resolve_library_page(self, url: str) -> str:
        """Resolve a library.lol/library.gift page to direct download URL."""
        client, request_url = await _make_client(url, connect_timeout=10.0, read_timeout=15.0)
        try:
            await _rate_limit()
            resp = await client.get(request_url)
            resp.raise_for_status()
        finally:
            await client.aclose()

        tree = lxml_html.fromstring(resp.text)

        # Try cloudflare IPFS
        for xpath in [
            "//a[contains(@href, 'cloudflare')]/@href",
            "//a[contains(@href, 'ipfs')]/@href",
            "//a[contains(text(), 'GET')]/@href",
        ]:
            links = tree.xpath(xpath)
            if links:
                return str(links[0])

        # Last resort: link ending with file extension
        for href in tree.xpath("//a/@href"):
            href = str(href).strip()
            if any(href.lower().endswith(ext) for ext in (".pdf", ".epub", ".cbz", ".cbr")):
                return href

        raise ValueError(f"Could not resolve download URL from {url}")

    # ---- File streaming --------------------------------------------------

    async def _stream_file(
        self, download_id: str, url: str, md5: str, dest_dir: str,
    ) -> str:
        """Stream download the actual file."""
        dest_path = Path(dest_dir)
        dest_path.mkdir(parents=True, exist_ok=True)

        client, request_url = await _make_client(url)
        try:
            await _rate_limit()
            logger.info("[AA stream] GET %s", request_url)
            async with client.stream("GET", request_url) as resp:
                resp.raise_for_status()
                ct = resp.headers.get("content-type", "")

                # If we got an HTML page instead of a file, something went wrong
                if "text/html" in ct:
                    body = ""
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        body += chunk.decode(errors="replace")
                        if len(body) > 50000:
                            break
                    raise ValueError(
                        f"Expected a file but got HTML from {url} "
                        f"(ct={ct}, body={body[:200]})"
                    )

                filename = self._extract_filename(resp.headers, md5)
                local_file = dest_path / filename
                self._downloads[download_id].name = filename

                total = int(resp.headers.get("content-length", 0))
                self._downloads[download_id].size = total
                logger.info("[AA stream] Streaming %d bytes -> %s", total, local_file)

                downloaded = 0
                start_time = time.monotonic()

                with open(local_file, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)

                        elapsed = time.monotonic() - start_time
                        speed = int(downloaded / elapsed) if elapsed > 0 else 0
                        progress = downloaded / total if total > 0 else 0.0
                        remaining = total - downloaded
                        eta = int(remaining / speed) if speed > 0 else 0

                        self._downloads[download_id].progress = progress
                        self._downloads[download_id].speed = speed
                        self._downloads[download_id].eta = eta
        finally:
            await client.aclose()

        self._downloads[download_id].status = "completed"
        self._downloads[download_id].progress = 1.0
        self._downloads[download_id].save_path = str(local_file)
        self._downloads[download_id].speed = 0
        self._downloads[download_id].eta = 0

        logger.info(
            "[AA stream] Done: %s (%d bytes)",
            local_file, local_file.stat().st_size,
        )
        return str(local_file)

    @staticmethod
    def _extract_filename(headers: httpx.Headers, md5: str) -> str:
        """Extract filename from Content-Disposition header."""
        cd = headers.get("content-disposition", "")
        if cd:
            match = re.search(r'filename[*]?="?([^";\n]+)"?', cd)
            if match:
                return match.group(1).strip()
        return f"{md5}.pdf"

    async def close(self) -> None:
        """Close the underlying HTTP clients."""
        await self._provider.close()
