"""telecharger-magazines.org scraper.

Three-step flow (the site is WordPress + a ``liens-direct.com``
redirector, NOT a DataLife Engine clone like Bookys):

1. WordPress default search ``GET /?s=<query>`` →
   results live inside ``<article class="result">`` elements
   with a heading-link to the magazine post page.
2. Magazine post page itself does NOT expose hoster URLs.
   It links once to ``https://new.liens-direct.com/<slug>.html``
   — that's the "links protector" page where the actual
   hosters live.
3. Follow the liens-direct URL, scrape every ``<a href>`` whose
   hostname matches a known file-hoster (``frdl.io``,
   ``rapidgator.net``, ``upfiles.com``, ``uploady.io``,
   ``dailyuploads.net``, …).

No login is required. Catalog overlap with Bookys is partial
(some niche FR titles only appear here), which is why we run
both providers in parallel and dedupe on ``(source, source_url)``.
"""

import asyncio
import logging
import re
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

# Article URLs look like /<category>/<slug>.html. The category
# segment varies (jeux-divers, presse, livres, …) so we anchor
# on the trailing ``.html`` rather than a fixed prefix.
_ARTICLE_RE = re.compile(r"/[a-z0-9-]+/[a-z0-9-]+\.html$", re.IGNORECASE)


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

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    async def search(self, query: str) -> list[MagazineSceneRelease]:
        if not query.strip():
            return []
        listing_html = await self._search_listing(query)
        if listing_html is None:
            return []
        urls = self._parse_listing_urls(listing_html)
        if not urls:
            logger.debug("tm.org returned no results for %r", query)
            return []
        # Cap per-query fanout — each result drags one article
        # fetch AND one liens-direct fetch, so we keep it tight.
        urls = urls[:6]

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
        """WordPress default search. ``?s=<query>`` is the
        cleanest endpoint — the site's ``index.php?do=search``
        looks like a stale DLE stub and just renders the
        homepage."""
        try:
            resp = await self._client.get(
                self.base_url + "/", params={"s": query}
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
        # WordPress search wraps each hit in
        # ``<article class="result">`` with a heading-link.
        # Fallback chain catches sites where that template
        # has been customised.
        candidates = tree.xpath(
            "//article[contains(@class,'result')]"
            "//*[self::h1 or self::h2 or self::h3]/a/@href"
        )
        if not candidates:
            # Last-resort: every anchor whose path matches the
            # /category/slug.html shape. Drops site nav, login
            # links, pagination.
            candidates = [
                h
                for h in tree.xpath("//a/@href")
                if _ARTICLE_RE.search(h or "")
            ]

        out: list[str] = []
        seen: set[str] = set()
        for h in candidates:
            absu = self._absolute(h)
            if absu and absu not in seen:
                seen.add(absu)
                out.append(absu)
        return out

    # ------------------------------------------------------------------
    # Release detail
    # ------------------------------------------------------------------
    async def _fetch_release(
        self, url: str
    ) -> MagazineSceneRelease | None:
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
        except Exception:
            logger.exception("tm.org release fetch failed: %s", url)
            return None

        try:
            tree = html.fromstring(resp.text)
        except Exception:
            logger.debug("tm.org release page parse failed: %s", url)
            return None

        title = self._first_text(
            tree,
            [
                "//meta[@property='og:title']/@content",
                "//h1//text()",
                "//title/text()",
            ],
        )
        title = self._clean_title(title) if title else url
        body_text = " ".join(
            tree.xpath(
                "//article//text() | "
                "//main//text() | "
                "//div[contains(@class,'entry-content')]//text()"
            )
        )
        cover_url = self._first_text(
            tree,
            [
                "//meta[@property='og:image']/@content",
                "//article//img/@src",
                "//main//img/@src",
            ],
        )
        cover_url = self._absolute(cover_url) if cover_url else None

        # Walk every liens-direct.com link found on the article
        # page and aggregate the hoster anchors each one exposes.
        # Most articles only have one redirector URL, but the
        # iteration costs nothing and survives the rare double-
        # mirror posts.
        protector_urls = self._collect_protector_urls(tree)
        if not protector_urls:
            logger.debug(
                "tm.org release %s exposed no liens-direct link", url
            )
            return None

        all_hosters: list[HosterLink] = []
        seen_links: set[str] = set()
        for prot_url in protector_urls:
            for hl in await self._extract_hosters(prot_url):
                if hl.url in seen_links:
                    continue
                seen_links.add(hl.url)
                all_hosters.append(hl)

        if not all_hosters:
            logger.debug(
                "tm.org release %s: liens-direct page exposed no known "
                "hosters",
                url,
            )
            return None

        return MagazineSceneRelease(
            source=self.name,
            source_url=url,
            title=title,
            hoster_links=all_hosters,
            issue_label=parse_issue_label(title),
            year=parse_year(title),
            language="fr",
            file_format=parse_format(title) or "pdf",
            size_bytes=parse_size_bytes(body_text),
            published_at=None,
            cover_url=cover_url,
        )

    def _collect_protector_urls(self, tree) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for href in tree.xpath("//a/@href"):
            if not href or "liens-direct" not in href:
                continue
            if href in seen:
                continue
            seen.add(href)
            out.append(href)
        return out

    async def _extract_hosters(self, protector_url: str) -> list[HosterLink]:
        try:
            resp = await self._client.get(protector_url)
            resp.raise_for_status()
        except Exception:
            logger.debug(
                "tm.org liens-direct fetch failed: %s",
                protector_url,
                exc_info=True,
            )
            return []
        try:
            tree = html.fromstring(resp.text)
        except Exception:
            return []
        hosters: list[HosterLink] = []
        seen: set[str] = set()
        for href in tree.xpath("//a/@href"):
            h = detect_hoster(href)
            if not h or href in seen:
                continue
            seen.add(href)
            hosters.append(HosterLink(hoster=h, url=href))
        return hosters

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------
    async def test_connection(self) -> tuple[bool, str]:
        try:
            resp = await self._client.get(self.base_url)
            resp.raise_for_status()
            return True, "telecharger-magazines.org: reachable"
        except Exception as e:
            return False, f"telecharger-magazines.org: probe failed ({e!s})"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _clean_title(self, title: str) -> str:
        """tm.org's ``<title>`` and ``og:title`` always append
        the site name suffix ("- Télécharger Des Magazines,
        Journaux et Livres Gratuitement"). Strip it so the UI
        doesn't render 40 characters of boilerplate per row."""
        t = (title or "").strip()
        # Both " - " and " – " (en-dash) variants appear in the
        # wild. Cut at the first separator preceding "télécharger".
        m = re.search(
            r"\s*[-–—]\s*Téléch?arger\s+Des\s+Magazines.*$",
            t,
            re.IGNORECASE,
        )
        if m:
            t = t[: m.start()].rstrip()
        return t

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
