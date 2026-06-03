"""telecharger-magazines.org scraper.

Same DataLife-Engine -shaped site as Bookys but without a
login wall. We post a search query, walk the listing, fetch
each release page, and pull the file-hoster anchors out of the
article body.

Because no credentials are needed the orchestrator can
fall back to this provider when Bookys is disabled or down —
catalog overlap is significant (both sites ride the same
French scene release calendar).
"""

import asyncio
import logging
from collections.abc import Iterable

import httpx
from lxml import html

from app.indexers.magazine_scene._html_utils import (
    detect_hoster,
    parse_format,
    parse_issue_label,
    parse_size_bytes,
    parse_year,
)
from app.indexers.magazine_scene.base import (
    HosterLink,
    MagazineSceneIndexerBase,
    MagazineSceneRelease,
)

logger = logging.getLogger(__name__)


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class TelechargerMagazinesIndexer(MagazineSceneIndexerBase):
    """telecharger-magazines.org HTML scraper."""

    name = "telecharger_magazines"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=25.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "fr,en;q=0.9",
            },
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def search(self, query: str) -> list[MagazineSceneRelease]:
        if not query.strip():
            return []
        listing_html = await self._search_listing(query)
        if listing_html is None:
            return []
        urls = self._parse_listing_urls(listing_html)[:8]
        if not urls:
            logger.debug("tm.org returned no results for %r", query)
            return []
        details = await asyncio.gather(
            *(self._fetch_release(u) for u in urls), return_exceptions=True
        )
        out: list[MagazineSceneRelease] = []
        for d in details:
            if isinstance(d, Exception):
                logger.debug("tm.org release fetch failed", exc_info=d)
                continue
            if d is not None:
                out.append(d)
        return out

    async def _search_listing(self, query: str) -> str | None:
        try:
            resp = await self._client.post(
                f"{self.base_url}/index.php?do=search",
                data={
                    "do": "search",
                    "subaction": "search",
                    "story": query,
                },
            )
            resp.raise_for_status()
            return resp.text
        except Exception:
            logger.exception(
                "tm.org listing fetch failed for query=%r", query
            )
            return None

    def _parse_listing_urls(self, html_text: str) -> list[str]:
        try:
            tree = html.fromstring(html_text)
        except Exception:
            return []
        candidates = tree.xpath(
            "//div[contains(@class,'short') or "
            "contains(@class,'base') or "
            "contains(@class,'news')]"
            "//*[self::h2 or self::h3 or self::h4]/a/@href"
        )
        seen: set[str] = set()
        out: list[str] = []
        for h in candidates:
            absu = self._absolute(h)
            if absu and absu not in seen:
                seen.add(absu)
                out.append(absu)
        return out

    async def _fetch_release(
        self, url: str
    ) -> MagazineSceneRelease | None:
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
        except Exception:
            logger.exception("tm.org release fetch failed: %s", url)
            return None
        return self._parse_release_page(url, resp.text)

    def _parse_release_page(
        self, url: str, html_text: str
    ) -> MagazineSceneRelease | None:
        try:
            tree = html.fromstring(html_text)
        except Exception:
            return None
        title = self._first_text(
            tree,
            [
                "//meta[@property='og:title']/@content",
                "//h1//text()",
                "//title/text()",
            ],
        )
        title = title.strip() if title else url
        body_text = " ".join(
            tree.xpath(
                "//div[contains(@class,'fdesc') or "
                "contains(@class,'maincont') or "
                "contains(@class,'fstory') or "
                "contains(@class,'fmain')]//text()"
            )
        )
        cover_url = self._first_text(
            tree,
            [
                "//meta[@property='og:image']/@content",
                "//div[contains(@class,'fmain')]//img/@src",
            ],
        )
        cover_url = self._absolute(cover_url) if cover_url else None

        hosters: list[HosterLink] = []
        seen: set[str] = set()
        for href in tree.xpath("//a/@href"):
            h = detect_hoster(href)
            if not h or href in seen:
                continue
            seen.add(href)
            hosters.append(HosterLink(hoster=h, url=href))
        if not hosters:
            logger.debug("tm.org release %s exposed no known hosters", url)
            return None

        return MagazineSceneRelease(
            source=self.name,
            source_url=url,
            title=title,
            hoster_links=hosters,
            issue_label=parse_issue_label(title),
            year=parse_year(title),
            language="fr",
            file_format=parse_format(title) or "pdf",
            size_bytes=parse_size_bytes(body_text),
            published_at=None,
            cover_url=cover_url,
        )

    async def test_connection(self) -> tuple[bool, str]:
        try:
            resp = await self._client.get(self.base_url)
            resp.raise_for_status()
            return True, "telecharger-magazines.org: reachable"
        except Exception as e:
            return False, f"telecharger-magazines.org: probe failed ({e!s})"

    def _absolute(self, href: str | None) -> str | None:
        if not href:
            return None
        if href.startswith(("http://", "https://")):
            return href
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return self.base_url + href
        return f"{self.base_url}/{href.lstrip('/')}"

    def _first_text(self, tree, xpaths: Iterable[str]) -> str | None:
        for xp in xpaths:
            try:
                vals = tree.xpath(xp)
            except Exception:
                continue
            for v in vals:
                if v is None:
                    continue
                s = (v if isinstance(v, str) else v.text_content()).strip()
                if s:
                    return s
        return None
