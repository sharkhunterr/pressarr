"""Anna's Archive search provider for magazine search via HTML scraping."""

import asyncio
import logging
import re

import httpx
from lxml import html

logger = logging.getLogger(__name__)

DEFAULT_MIRROR = "annas-archive.li"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class AnnasArchiveProvider:
    """Search Anna's Archive by scraping HTML results."""

    def __init__(self, mirror: str = DEFAULT_MIRROR):
        self.mirror = mirror
        self._client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._rate_limiter = asyncio.Semaphore(1)
        self._last_request_time: float = 0.0

    async def _rate_limited_get(self, url: str, **kwargs) -> httpx.Response:
        """Make a rate-limited GET request (max 1 req/sec)."""
        async with self._rate_limiter:
            now = asyncio.get_event_loop().time()
            wait = self._last_request_time + 1.0 - now
            if wait > 0:
                await asyncio.sleep(wait)
            resp = await self._client.get(url, **kwargs)
            self._last_request_time = asyncio.get_event_loop().time()
            return resp

    async def search(self, query: str, page: int = 1) -> list[dict]:
        """Search Anna's Archive for magazines.

        Returns a list of dicts with keys:
            md5, title, author, publisher, thumbnail, language, format, size, year, url
        """
        url = f"https://{self.mirror}/search"
        params = {
            "q": query,
            "content": "magazine",
            "ext": "pdf",
            "sort": "newest",
            "page": str(page),
        }

        try:
            resp = await self._rate_limited_get(url, params=params)
            resp.raise_for_status()
        except Exception:
            logger.exception("Anna's Archive search failed for query=%s", query)
            return []

        return self._parse_search_html(resp.text)

    def _parse_search_html(self, html_text: str) -> list[dict]:
        """Parse search results from AA HTML using lxml XPaths."""
        results: list[dict] = []

        try:
            tree = html.fromstring(html_text)
        except Exception:
            logger.exception("Failed to parse AA HTML")
            return []

        # Each result is a div inside the main aarecord list
        containers = tree.xpath(
            "//main//div[contains(@class, 'js-aarecord-list-outer')]/div"
        )

        for container in containers:
            try:
                result = self._parse_single_result(container)
                if result:
                    results.append(result)
            except Exception:
                logger.debug("Failed to parse AA result element", exc_info=True)
                continue

        return results

    def _parse_single_result(self, el) -> dict | None:
        """Parse a single search result element.

        AA HTML structure per result:
          <a href="/md5/...">  (cover image wrapper)
          <div>
            <div class="text-gray-500 font-mono">path/file.pdf</div>
            <a href="/md5/..." class="font-semibold text-lg">Title</a>
            <a href="/search?q=">Publisher, #N, year</a>
          </div>
          <div class="font-semibold text-sm">
            French [fr] · PDF · 109.8MB · 2023 · ...
          </div>
        """
        # All md5 links in this container
        md5_links = el.xpath(".//a[starts-with(@href, '/md5')]")
        if not md5_links:
            return None

        # Extract MD5 from first link
        href = md5_links[0].get("href", "")
        md5_match = re.search(r"/md5/([a-fA-F0-9]+)", href)
        if not md5_match:
            return None
        md5 = md5_match.group(1).lower()

        # Title: the md5 link that has text (not the cover image one)
        title = ""
        for link in md5_links:
            text = (link.text_content() or "").strip()
            if text:
                title = text
                break

        # Fallback: try the fallback cover data-content attribute
        if not title:
            fallback = el.xpath(
                ".//div[contains(@class, 'js-aarecord-list-fallback')]"
                "//div[@data-content]/@data-content"
            )
            if fallback:
                title = str(fallback[0]).strip()

        # Publisher/author line: <a href="/search?q=">
        search_links = el.xpath(
            ".//a[starts-with(@href, '/search')]"
        )
        publisher = ""
        if search_links:
            publisher = (
                search_links[0].text_content() or ""
            ).strip()

        # Thumbnail
        img_els = el.xpath(".//img/@src")
        thumbnail = str(img_els[0]) if img_els else ""

        # Metadata line: "French [fr] · PDF · 109.8MB · 2023 · ..."
        # It's in a div with classes font-semibold + text-sm
        meta_els = el.xpath(
            ".//div[contains(@class, 'font-semibold')"
            " and contains(@class, 'text-sm')]"
        )
        language = ""
        file_format = "pdf"
        size = ""
        year = ""

        for meta_el in meta_els:
            meta_text = (meta_el.text_content() or "").strip()
            if not meta_text:
                continue
            # Split on middle-dot separator "·"
            parts = [p.strip() for p in re.split(r"\s*·\s*", meta_text)]
            for part in parts:
                p = part.strip()
                p_lower = p.lower()
                # Language: "French [fr]" or "English [en]"
                lang_m = re.match(
                    r"^([A-Za-z]+)\s*\[[a-z]{2,3}\]$", p
                )
                if lang_m:
                    language = lang_m.group(1)
                    continue
                # Size: "109.8MB"
                if re.match(
                    r"^[\d.]+\s*(kb|mb|gb|tb|bytes?)$",
                    p_lower,
                ):
                    size = p
                    continue
                # Year: bare 4-digit number
                if re.match(r"^\d{4}$", p):
                    year = p
                    continue
                # Format: PDF, EPUB, etc.
                if p_lower in (
                    "pdf", "epub", "cbz", "cbr", "djvu", "mobi",
                ):
                    file_format = p_lower
                    continue

        return {
            "md5": md5,
            "title": title or md5,
            "author": "",
            "publisher": publisher,
            "thumbnail": thumbnail,
            "language": language,
            "format": file_format,
            "size": size,
            "year": year,
            "url": f"https://{self.mirror}/md5/{md5}",
        }

    async def get_download_links(self, md5: str) -> list[str]:
        """Fetch the MD5 detail page and extract direct download links."""
        url = f"https://{self.mirror}/md5/{md5}"

        try:
            resp = await self._rate_limited_get(url)
            resp.raise_for_status()
        except Exception:
            logger.exception("Failed to fetch AA detail page for md5=%s", md5)
            return []

        return self._parse_download_links(resp.text)

    def _parse_download_links(self, html_text: str) -> list[str]:
        """Extract direct download links from the AA MD5 detail page.

        AA detail pages have multiple download options organized in
        sections. We look for all external links that look like they
        lead to actual file downloads across various mirrors.
        """
        links: list[str] = []
        seen: set[str] = set()

        try:
            tree = html.fromstring(html_text)
        except Exception:
            logger.exception("Failed to parse AA detail page HTML")
            return []

        all_hrefs = tree.xpath("//a/@href")
        logger.info(
            "[AA links] Found %d total hrefs on detail page", len(all_hrefs)
        )

        # Keywords that indicate a download mirror/link
        download_keywords = [
            "libgen",
            "library.lol",
            "library.gift",
            "cloudflare-ipfs",
            "ipfs.io",
            "pinata",
            "get.php",
            "file.php",
            "download",
            "slow_download",
            "fast_download",
            "/dl/",
        ]
        # Keywords to exclude (navigation, search, etc.)
        exclude_keywords = [
            "/search",
            "/md5/",
            "javascript:",
            "#",
            "annas-archive",
            "anna-hierarchical",
        ]

        for href in all_hrefs:
            href = str(href).strip()
            if not href or href in seen:
                continue
            # Must be an absolute URL
            if not href.startswith("http"):
                continue
            # Skip self-referencing / navigation links
            if any(excl in href for excl in exclude_keywords):
                continue
            # Check if it matches any download keyword
            if any(kw in href.lower() for kw in download_keywords):
                seen.add(href)
                links.append(href)

        # If nothing matched with keywords, collect ALL external http links
        # as a last resort (the page might use new mirror domains)
        if not links:
            for href in all_hrefs:
                href = str(href).strip()
                if (
                    href.startswith("http")
                    and href not in seen
                    and not any(excl in href for excl in exclude_keywords)
                ):
                    seen.add(href)
                    links.append(href)

        logger.info("[AA links] Extracted %d download links: %s", len(links), links)
        return links

    async def test_connection(self) -> tuple[bool, str]:
        """Test connectivity to the configured AA mirror."""
        try:
            resp = await self._rate_limited_get(f"https://{self.mirror}/")
            if resp.status_code == 200:
                return True, f"Connected to Anna's Archive ({self.mirror})"
            return False, f"Anna's Archive returned status {resp.status_code}"
        except Exception as e:
            return False, str(e)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
