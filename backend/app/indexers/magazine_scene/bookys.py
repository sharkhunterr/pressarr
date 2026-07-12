"""Bookys scene-magazine scraper.

The current Bookys host (``www6.bookys-ebooks.com``, the
operator-configured default) is behind Cloudflare's
"Just a moment…" JS challenge. A plain ``httpx`` GET gets a
403 with the interstitial HTML — no real content.

We solve that by routing every request through a FlareSolverr
sidecar (same one grabarr uses). FlareSolverr drives a headless
Chromium that runs Cloudflare's challenge, hands us the
post-challenge cookies, and then transparently proxies our
GET / POST against the target site.

Login flow inside a single FlareSolverr session:

1. ``sessions.create`` → fresh Chromium tab.
2. ``request.get`` on the login page (warms cookies +
   discovers any one-shot CSRF token the form might require).
3. ``request.post`` to the same login endpoint with the
   credentials. Success = a ``dle_user_id`` cookie shows up
   in the session jar.
4. ``request.post`` to ``/index.php?do=search`` for the
   actual query, parse the resulting HTML.
5. ``request.get`` on each release page, parse hoster links
   the same way ``telecharger_magazines`` does (URL-pattern
   matching, no DOM-position assumptions).

When no FlareSolverr endpoint is configured, the scraper logs
a warning and returns ``[]`` — pressarr keeps working with
``telecharger_magazines`` only.
"""

import asyncio
import logging
import re
from collections.abc import Iterable

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
from app.services.flaresolverr import (
    FlareSolverrClient,
    FlareSolverrError,
)

logger = logging.getLogger(__name__)


# Article URL shape on Bookys is /<digits>-<slug>.html (classic
# DLE). Used as a sieve when the listing template doesn't surface
# heading-links cleanly.
_ARTICLE_RE = re.compile(r"/\d+[-_][\w\-]+\.html$", re.IGNORECASE)


class BookysIndexer(MagazineSceneIndexerBase):
    """Bookys HTML scraper, all traffic via FlareSolverr."""

    name = "bookys"

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        flaresolverr: FlareSolverrClient | None,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._flare = flaresolverr
        # One FlareSolverr session per indexer instance. Created
        # lazily on first request, destroyed on close().
        self._session_id: str | None = None
        self._session_lock = asyncio.Lock()
        self._logged_in = False

    async def close(self) -> None:
        if self._flare and self._session_id:
            await self._flare.destroy_session(self._session_id)
            self._session_id = None
        if self._flare:
            await self._flare.close()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    async def _ensure_session(self) -> str | None:
        """Make sure the FlareSolverr session exists. Returns
        the session id or ``None`` when bypass isn't available
        (config missing or sidecar unreachable)."""
        if not self._flare:
            return None
        if self._session_id is not None:
            return self._session_id
        async with self._session_lock:
            if self._session_id is not None:
                return self._session_id
            sess_name = f"pressarr-bookys-{id(self) & 0xFFFFFF:x}"
            try:
                self._session_id = await self._flare.create_session(sess_name)
                return self._session_id
            except FlareSolverrError:
                logger.warning(
                    "Bookys: FlareSolverr session creation failed — bypass "
                    "disabled for this run"
                )
                return None

    async def _ensure_login(self) -> bool:
        if not self.username or not self.password:
            logger.debug(
                "Bookys credentials not configured — skipping login"
            )
            return False
        sess = await self._ensure_session()
        if not sess or not self._flare:
            return False
        if self._logged_in:
            return True

        try:
            # Warm the form so any CSRF cookie is set.
            await self._flare.request_get(
                f"{self.base_url}/index.php?do=login", session=sess
            )
            sol = await self._flare.request_post(
                f"{self.base_url}/index.php?do=login",
                post_data=(
                    f"login_name={_url_encode(self.username)}"
                    f"&login_password={_url_encode(self.password)}"
                    "&login_not_save=0&login=submit"
                ),
                session=sess,
            )
        except FlareSolverrError as e:
            logger.warning("Bookys login round-trip failed: %s", e)
            return False

        cookies = sol.get("cookies") or []
        has_auth_cookie = any(
            (c.get("name") or "").startswith("dle_user_id") for c in cookies
        )
        if not has_auth_cookie:
            logger.warning(
                "Bookys login did not set dle_user_id cookie — credentials "
                "wrong or site auth changed (response status=%s)",
                sol.get("status"),
            )
            return False
        self._logged_in = True
        logger.info("Bookys login OK as %s", self.username)
        return True

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    async def search(self, query: str) -> list[MagazineSceneRelease]:
        if not query.strip():
            return []
        if not await self._ensure_login():
            return []
        assert self._flare and self._session_id

        try:
            sol = await self._flare.request_post(
                f"{self.base_url}/index.php?do=search",
                post_data=(
                    "do=search&subaction=search&story="
                    f"{_url_encode(query)}"
                ),
                session=self._session_id,
            )
        except FlareSolverrError as e:
            logger.warning("Bookys search POST failed for %r: %s", query, e)
            return []
        listing_html = sol.get("response") or ""
        listing_urls = self._parse_listing_urls(listing_html)[:8]
        if not listing_urls:
            logger.debug("Bookys returned no results for %r", query)
            return []

        details = await asyncio.gather(
            *(self._fetch_release(u) for u in listing_urls),
            return_exceptions=True,
        )
        out: list[MagazineSceneRelease] = []
        for d in details:
            if isinstance(d, Exception):
                logger.debug("Bookys release fetch failed", exc_info=d)
                continue
            if d is not None:
                out.append(d)
        return out

    def _parse_listing_urls(self, html_text: str) -> list[str]:
        if not html_text:
            return []
        try:
            tree = html.fromstring(html_text)
        except Exception:
            return []
        candidates = tree.xpath(
            "//div[contains(@class,'short') or "
            "contains(@class,'base') or "
            "contains(@class,'story')]"
            "//*[self::h2 or self::h3 or self::h4]/a/@href"
        )
        if not candidates:
            candidates = [
                h
                for h in tree.xpath("//a/@href")
                if _ARTICLE_RE.search(h or "")
            ]
        out: list[str] = []
        seen: set[str] = set()
        for href in candidates:
            absu = self._absolute(href)
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
        assert self._flare and self._session_id
        try:
            sol = await self._flare.request_get(
                url, session=self._session_id
            )
        except FlareSolverrError as e:
            logger.debug("Bookys release fetch failed: %s (%s)", url, e)
            return None
        body = sol.get("response") or ""
        if not body:
            return None
        try:
            tree = html.fromstring(body)
        except Exception:
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

        hosters: list[HosterLink] = []
        seen: set[str] = set()
        for href in tree.xpath("//a/@href"):
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
        if not self._flare:
            return False, "Bookys: FlareSolverr endpoint not configured"
        if not self.username or not self.password:
            return False, "Bookys: credentials not configured"
        ok = await self._ensure_login()
        if not ok:
            return False, "Bookys: login refused"
        return True, "Bookys: connected"

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


def _url_encode(s: str) -> str:
    """``urllib.parse.quote`` with the safe-char set FlareSolverr
    expects in ``postData`` (no spaces, no &/=)."""
    from urllib.parse import quote
    return quote(s, safe="")
