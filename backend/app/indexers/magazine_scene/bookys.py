"""Bookys scene-magazine scraper.

Bookys-gratuit.com publishes French magazine releases (PDF
mostly) behind a free account. Each release page has the
file-hoster links visible in the article body once the user is
logged in.

Site engine is DataLife Engine ("DLE"). The login endpoint is
``/index.php?do=login`` and the search endpoint is
``/index.php?do=search`` (POST with ``story`` + ``do=search``).
DLE is widely cloned by French scene sites, so the same scraper
pattern often works for similar mirrors.

We keep the parser DEFENSIVE:
- Login is lazy: the first request that finds itself logged out
  re-authenticates and retries once.
- Selectors are loose (``//div[contains(@class, 'short')]``)
  with multiple fallbacks; on parse miss the scraper logs the
  raw fragment + returns ``[]`` instead of crashing.
- Hoster links are extracted by URL pattern matching, not
  position in the DOM — DLE templates move them around a lot.
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


class BookysIndexer(MagazineSceneIndexerBase):
    """Bookys-gratuit.com HTML scraper."""

    name = "bookys"

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        # Single shared client per indexer instance so the auth
        # cookies persist across search → detail roundtrips.
        # ``follow_redirects`` is on because DLE's login bounces
        # twice (set-cookie then redirect to home).
        self._client = httpx.AsyncClient(
            timeout=25.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "fr,en;q=0.9",
            },
            follow_redirects=True,
        )
        self._logged_in = False
        # Serialise the login dance — two concurrent searches
        # racing through the auth endpoint would each set a
        # different cookie and one would lose.
        self._auth_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    async def _ensure_login(self, force: bool = False) -> bool:
        """Log in once (or re-login on ``force``). Returns True
        on success. Credentials missing → False without any
        request, so the orchestrator can short-circuit the
        provider when the operator hasn't filled the settings."""
        if not self.username or not self.password:
            logger.debug("Bookys credentials not configured — skipping login")
            return False
        if self._logged_in and not force:
            return True
        async with self._auth_lock:
            if self._logged_in and not force:
                return True
            try:
                # DLE's login form posts to /index.php?do=login&doaction=
                # but most templates accept the simpler /index.php?do=login.
                # ``login=submit`` is the magic key DLE expects to know
                # it's a credentials submit (vs the form-render GET).
                resp = await self._client.post(
                    f"{self.base_url}/index.php?do=login",
                    data={
                        "login_name": self.username,
                        "login_password": self.password,
                        "login_not_save": "0",
                        "login": "submit",
                    },
                )
                # DLE returns 200 on both success and failure;
                # success → the response sets a ``dle_user_id``
                # cookie. We rely on that instead of HTML
                # scraping the page (templates vary too much).
                cookies = {c.name for c in self._client.cookies.jar}
                if any(c.startswith("dle_user_id") for c in cookies):
                    self._logged_in = True
                    logger.info("Bookys login OK as %s", self.username)
                    return True
                logger.warning(
                    "Bookys login response did not set dle_user_id cookie "
                    "(status=%s). Check credentials or site auth changes.",
                    resp.status_code,
                )
                return False
            except Exception:
                logger.exception("Bookys login failed")
                return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    async def search(self, query: str) -> list[MagazineSceneRelease]:
        if not query.strip():
            return []
        if not await self._ensure_login():
            return []

        listing_html = await self._search_listing(query)
        if listing_html is None:
            return []

        listing_urls = self._parse_listing_urls(listing_html)
        if not listing_urls:
            logger.debug("Bookys listing returned no results for %r", query)
            return []

        # Cap the per-query fanout — operator-typed queries
        # sometimes match hundreds of unrelated releases on
        # Bookys, and each detail fetch costs an HTTP roundtrip.
        # Capping to 8 lines up with the orchestrator's "show
        # the operator a digestible list" goal.
        listing_urls = listing_urls[:8]

        details = await asyncio.gather(
            *(self._fetch_release(url) for url in listing_urls),
            return_exceptions=True,
        )
        releases: list[MagazineSceneRelease] = []
        for d in details:
            if isinstance(d, Exception):
                logger.debug("Bookys release fetch failed", exc_info=d)
                continue
            if d is not None:
                releases.append(d)
        return releases

    async def _search_listing(self, query: str) -> str | None:
        """POST the DLE search form and return the raw HTML.
        Re-authenticates once on 403/redirect-to-login."""
        for attempt in (1, 2):
            try:
                resp = await self._client.post(
                    f"{self.base_url}/index.php?do=search",
                    data={
                        "do": "search",
                        "subaction": "search",
                        "story": query,
                    },
                )
                if resp.status_code == 403 and attempt == 1:
                    await self._ensure_login(force=True)
                    continue
                resp.raise_for_status()
                return resp.text
            except Exception:
                logger.exception(
                    "Bookys listing fetch failed (attempt=%d query=%r)",
                    attempt, query,
                )
                if attempt == 2:
                    return None
        return None

    def _parse_listing_urls(self, html_text: str) -> list[str]:
        """DLE listings look like ``<div class="short">`` with
        a title-link inside. Some Bookys templates use
        ``.base`` or ``.story``; the XPath is tolerant."""
        try:
            tree = html.fromstring(html_text)
        except Exception:
            logger.debug("Bookys listing HTML parse failed")
            return []
        # Title links inside the listing items. Most DLE skins
        # wrap them in ``h2`` / ``h3`` inside the short block;
        # falling back to any inline link with ``/<digits>-…``
        # path catches alternative skins.
        candidates = tree.xpath(
            "//div[contains(@class,'short') or "
            "contains(@class,'base') or "
            "contains(@class,'story')]"
            "//*[self::h2 or self::h3 or self::h4]/a/@href"
        )
        if not candidates:
            candidates = tree.xpath(
                "//a[contains(@href, '/index.php') = false()][re:match"
                "(@href, '/(\\d+)-[\\w-]+\\.html$')]/@href",
                namespaces={"re": "http://exslt.org/regular-expressions"},
            )
        # Normalise to absolute URLs and dedupe in order.
        out: list[str] = []
        seen: set[str] = set()
        for href in candidates:
            absu = self._absolute(href)
            if absu and absu not in seen:
                seen.add(absu)
                out.append(absu)
        return out

    async def _fetch_release(self, url: str) -> MagazineSceneRelease | None:
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
        except Exception:
            logger.exception("Bookys release page fetch failed: %s", url)
            return None
        return self._parse_release_page(url, resp.text)

    def _parse_release_page(
        self, url: str, html_text: str
    ) -> MagazineSceneRelease | None:
        try:
            tree = html.fromstring(html_text)
        except Exception:
            logger.debug("Bookys release page parse failed: %s", url)
            return None

        title = self._first_text(
            tree,
            [
                "//meta[@property='og:title']/@content",
                "//h1[contains(@class,'storytitle')]//text()",
                "//h1//text()",
                "//title/text()",
            ],
        )
        title = title.strip() if title else url

        body_text = " ".join(
            tree.xpath(
                "//div[contains(@class,'maincont') or "
                "contains(@class,'fdesc') or contains(@class,'fstory')]"
                "//text()"
            )
        )
        cover_url = self._first_text(
            tree,
            [
                "//meta[@property='og:image']/@content",
                "//div[contains(@class,'fmain')]//img/@src",
                "//div[contains(@class,'maincont')]//img/@src",
            ],
        )
        cover_url = self._absolute(cover_url) if cover_url else None

        # Pull every <a href> that maps to a known hoster.
        # DLE templates sometimes wrap links in JS popups
        # (``href="#" onclick="window.open(...)"``); the URL
        # still lives in the rendered HTML so the simple href
        # pass catches the majority.
        hoster_anchors = tree.xpath("//a/@href")
        hosters: list[HosterLink] = []
        seen: set[str] = set()
        for href in hoster_anchors:
            h = detect_hoster(href)
            if not h or href in seen:
                continue
            seen.add(href)
            hosters.append(HosterLink(hoster=h, url=href))
        if not hosters:
            logger.debug("Bookys release %s exposed no known hosters", url)
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

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------
    async def test_connection(self) -> tuple[bool, str]:
        if not self.username or not self.password:
            return False, "Bookys: credentials not configured"
        ok = await self._ensure_login(force=True)
        if not ok:
            return False, "Bookys: login refused"
        try:
            # Cheap sanity probe — fetch the homepage and check
            # the auth cookie survived.
            resp = await self._client.get(self.base_url)
            resp.raise_for_status()
            return True, "Bookys: connected"
        except Exception as e:
            return False, f"Bookys: probe failed ({e!s})"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
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
