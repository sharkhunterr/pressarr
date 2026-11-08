"""Bookys scene-magazine scraper.

The current Bookys host (``www7.bookys-ebooks.com`` since
October 2026 — ``www6`` redirects there — the
operator-configured default) is a Laravel site behind
Cloudflare's "Just a moment…" JS challenge. A plain ``httpx``
GET gets a 403 — and a plain client carrying the clearance
cookie a browser earned is soon refused too ("Access denied",
error 1106).

So every page goes through one FlareSolverr session — a real
Chromium tab: the first request solves the challenge (10 to 60
s), the next ones take about half a second. They run one at a
time, which also keeps the site from answering 429.

No account is needed: the search, the release pages and their
``/dl/`` pages are public. (Signing in could not work through
FlareSolverr anyway: its ``request.post`` submits from a
``data:`` page, the browser withholds the SameSite session
cookie and Laravel answers "Page Expired".) The username and
password stay in the settings but are not used.

Flow:

1. ``GET /search?q=…`` → the ``#search_table`` rows; only the
   ``/journaux/`` and ``/magazines/`` entries are kept.
2. ``GET`` each release page → its download table (Type,
   Format, Langue, Taille, Part), one ``…/dl/<id>`` link per
   hoster; each ``/dl/`` page holds the real hoster URL.

When no FlareSolverr endpoint is configured, the scraper returns
``[]`` — pressarr keeps working with ``telecharger_magazines``
only.
"""

import asyncio
import logging
import re
from collections.abc import Iterable
from urllib.parse import quote

from lxml import etree, html

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


# Release pages worth a look: /journaux/<id>-<slug> and
# /magazines/<id>-<slug> (books, comics and software share the
# search but are not Pressarr's business).
_RELEASE_RE = re.compile(r"/(?:journaux|magazines)/\d+-[\w-]+/?$")
_DL_RE = re.compile(r"/dl/\d+/?$")
_URL_RE = re.compile(r"""https?://[^\s"'<>]+""")
_SEARCH_LIMIT = 8
_LANGUAGES = {"français": "fr", "francais": "fr", "anglais": "en"}


class BookysIndexer(MagazineSceneIndexerBase):
    """Bookys HTML scraper, every page through one FlareSolverr
    session."""

    name = "bookys"

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        flaresolverr: FlareSolverrClient | None,
    ):
        self.base_url = base_url.rstrip("/")
        # Kept for the settings round-trip; the site needs no account.
        self.username = username
        self.password = password
        self._flare = flaresolverr
        # One Chromium tab per indexer instance, created lazily,
        # destroyed by close(); one request at a time in it.
        self._session_id: str | None = None
        self._session_lock = asyncio.Lock()
        self._tab = asyncio.Lock()
        # A scan searches the title and its aliases: the same
        # release pages come back, fetch them once.
        self._releases: dict[str, MagazineSceneRelease | None] = {}
        # Why the last page could not be fetched, for the connection test.
        self._error = "site unreachable"

    async def close(self) -> None:
        if self._flare and self._session_id:
            await self._flare.destroy_session(self._session_id)
            self._session_id = None
        if self._flare:
            await self._flare.close()

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    async def _ensure_session(self) -> str | None:
        if not self._flare:
            self._error = "FlareSolverr endpoint not configured"
            return None
        if self._session_id is not None:
            return self._session_id
        async with self._session_lock:
            if self._session_id is not None:
                return self._session_id
            try:
                self._session_id = await self._flare.create_session(
                    f"pressarr-bookys-{id(self) & 0xFFFFFF:x}"
                )
            except FlareSolverrError as e:
                self._error = f"FlareSolverr unreachable ({e})"
                return None
            return self._session_id

    async def _get(self, url: str) -> str | None:
        """The page's HTML, or ``None`` (reason in ``_error``)."""
        session = await self._ensure_session()
        if session is None or self._flare is None:
            return None
        async with self._tab:
            try:
                sol = await self._flare.request_get(url, session=session)
            except FlareSolverrError as e:
                logger.warning("Bookys: FlareSolverr failed on %s: %s", url, e)
                self._error = (
                    f"FlareSolverr could not get past the site's protection ({e})"
                )
                return None
        status = sol.get("status")
        if status != 200:
            logger.debug("Bookys fetch %s answered %s", url, status)
            self._error = f"the site answered {status}"
            return None
        return sol.get("response") or None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    async def search(self, query: str) -> list[MagazineSceneRelease]:
        if not query.strip():
            return []
        page = await self._get(f"{self.base_url}/search?q={quote(query)}")
        if page is None:
            logger.warning("Bookys search failed for %r: %s", query, self._error)
            return []
        listing_urls = self._parse_listing_urls(page)[:_SEARCH_LIMIT]
        if not listing_urls:
            logger.debug("Bookys returned no results for %r", query)
            return []

        out: list[MagazineSceneRelease] = []
        for url in listing_urls:
            if url not in self._releases:
                try:
                    self._releases[url] = await self._fetch_release(url)
                except Exception:
                    logger.debug("Bookys release fetch failed: %s", url, exc_info=True)
                    self._releases[url] = None
            release = self._releases[url]
            if release is not None:
                out.append(release)
        return out

    def _parse_listing_urls(self, html_text: str) -> list[str]:
        """Release links of the search results table, in the
        site's order — the side columns list unrelated releases."""
        try:
            tree = html.fromstring(html_text)
        except (ValueError, etree.ParserError):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for href in tree.xpath("//table[@id='search_table']//a/@href"):
            absu = self._absolute(href)
            if absu and _RELEASE_RE.search(absu) and absu not in seen:
                seen.add(absu)
                out.append(absu)
        return out

    # ------------------------------------------------------------------
    # Release detail
    # ------------------------------------------------------------------
    async def _fetch_release(
        self, url: str
    ) -> MagazineSceneRelease | None:
        body = await self._get(url)
        if not body:
            return None
        try:
            tree = html.fromstring(body)
        except (ValueError, etree.ParserError):
            return None

        title = self._first_text(
            tree, ["//h1//text()", "//title/text()"]
        )
        title = title.strip() if title else url

        # One row per hoster: Type | Format | Langue | Taille | Part.
        rows: list[tuple[str, list[str]]] = []
        for a in tree.xpath("//a[@href]"):
            dl = self._absolute(a.get("href"))
            if not dl or not _DL_RE.search(dl):
                continue
            tr = a.xpath("ancestor::tr[1]")
            cells = (
                [" ".join(td.text_content().split()) for td in tr[0].xpath("./td")]
                if tr
                else []
            )
            rows.append((dl, cells))
        if not rows:
            logger.debug("Bookys release %s exposed no download links", url)
            return None

        hosters: list[HosterLink] = []
        seen: set[str] = set()
        for dl, _ in rows:
            link = await self._resolve_dl(dl)
            if link and link.url not in seen:
                seen.add(link.url)
                hosters.append(link)
        if not hosters:
            logger.debug("Bookys release %s exposed no known hosters", url)
            return None

        cells = rows[0][1]
        file_format = cells[1].lower() if len(cells) > 1 and cells[1] else None
        language = (
            _LANGUAGES.get(cells[2].lower(), cells[2].lower()[:5])
            if len(cells) > 2 and cells[2]
            else "fr"
        )
        size_text = cells[3] if len(cells) > 3 else None

        return MagazineSceneRelease(
            source=self.name,
            source_url=url,
            title=title,
            hoster_links=hosters,
            issue_label=parse_issue_label(title),
            year=parse_year(title),
            language=language,
            file_format=file_format or parse_format(title) or "pdf",
            size_bytes=parse_size_bytes(size_text),
            published_at=None,
            # The site's covers (/storage/items/…) answer 403 without
            # the Cloudflare clearance: a browser would show them broken.
            cover_url=None,
        )

    async def _resolve_dl(self, dl_url: str) -> HosterLink | None:
        """The hoster URL a ``…/dl/<id>`` page hands out."""
        body = await self._get(dl_url)
        if not body:
            return None
        for url in _URL_RE.findall(body):
            hoster = detect_hoster(url)
            if hoster:
                return HosterLink(hoster=hoster, url=url)
        return None

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------
    async def test_connection(self) -> tuple[bool, str]:
        if not self._flare:
            return False, "Bookys: FlareSolverr endpoint not configured"
        page = await self._get(f"{self.base_url}/search?q=le")
        if page is None:
            return False, f"Bookys: {self._error}"
        if "search_table" not in page:
            return False, "Bookys: the search page changed — the scraper needs an update"
        return True, "Bookys: connected (no account needed)"

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
