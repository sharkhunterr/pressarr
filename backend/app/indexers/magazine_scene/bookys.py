"""Bookys scene-magazine scraper.

The current Bookys host (``www7.bookys-ebooks.com`` since
October 2026 — ``www6`` redirects there — the
operator-configured default) is a Laravel site behind
Cloudflare's "Just a moment…" JS challenge. A plain ``httpx``
GET gets a 403 with the interstitial HTML — no real content.

FlareSolverr (same sidecar grabarr uses) only solves that
challenge: one ``request.get`` hands back the ``cf_clearance``
cookie and the User-Agent it was issued to. Everything else runs
on a plain ``httpx`` client carrying both — the clearance holds
as long as Pressarr and FlareSolverr leave from the same public
IP. Logging in through FlareSolverr's own ``request.post`` cannot
work: it submits from a ``data:`` page, so the browser withholds
the SameSite session cookie and Laravel answers "Page Expired".

Flow:

1. FlareSolverr ``request.get`` on ``/login`` → clearance + UA.
2. ``GET /login`` → the form's action and its one-shot
   ``_token``; ``POST`` ``_token`` / ``username`` / ``password``
   / ``remember``. Success = a page with a logout link and no
   password field. A refusal reads "Aucun utilisateur trouvé
   pour les identifiants fournis".
3. ``GET /search?q=…`` → the ``#search_table`` rows; only the
   ``/journaux/`` and ``/magazines/`` entries are kept.
4. ``GET`` each release page → its download table (Type,
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

import httpx
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
# Release + /dl/ pages fetched at once — a search fans out to
# about 8 releases × 3 hosters.
_CONCURRENCY = 4
_LANGUAGES = {"français": "fr", "francais": "fr", "anglais": "en"}


class BookysIndexer(MagazineSceneIndexerBase):
    """Bookys HTML scraper: FlareSolverr for the Cloudflare
    clearance, plain httpx for the rest."""

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
        # Built lazily from the FlareSolverr clearance, closed by close().
        self._client: httpx.AsyncClient | None = None
        self._login_lock = asyncio.Lock()
        self._fetch_slots = asyncio.Semaphore(_CONCURRENCY)
        self._logged_in = False
        # Why the last login attempt failed, for the connection test.
        self._login_error = "login refused"

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._flare:
            await self._flare.close()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    async def _ensure_client(self) -> httpx.AsyncClient | None:
        """An httpx client carrying the Cloudflare clearance
        FlareSolverr obtained, or ``None`` when it could not."""
        if self._client is not None:
            return self._client
        if not self._flare:
            self._login_error = "FlareSolverr endpoint not configured"
            return None
        try:
            sol = await self._flare.request_get(f"{self.base_url}/login")
        except FlareSolverrError as e:
            logger.warning("Bookys: FlareSolverr failed: %s", e)
            self._login_error = (
                f"FlareSolverr could not get past the site's protection ({e})"
            )
            return None
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": sol.get("userAgent") or "",
                "Accept-Language": "fr-FR,fr;q=0.9",
            },
            cookies={
                c["name"]: c.get("value", "")
                for c in sol.get("cookies") or []
                if c.get("name")
            },
            follow_redirects=True,
            timeout=30.0,
        )
        return self._client

    async def _ensure_login(self) -> bool:
        if not self.username or not self.password:
            self._login_error = "credentials not configured"
            return False
        if self._logged_in:
            return True
        async with self._login_lock:
            if self._logged_in:
                return True
            client = await self._ensure_client()
            if client is None:
                return False
            try:
                page = await client.get(f"{self.base_url}/login")
                if _blocked(page):
                    self._login_error = (
                        "Cloudflare refused the clearance FlareSolverr "
                        "obtained — Pressarr and FlareSolverr must reach "
                        "the site from the same public IP"
                    )
                    return False
                form = _login_form(page.text, self.base_url)
                answer = await client.post(
                    form.action,
                    data={
                        "_token": form.token or "",
                        "username": self.username,
                        "password": self.password,
                        "remember": "on",
                    },
                    headers={"Referer": f"{self.base_url}/login"},
                )
            except httpx.HTTPError as e:
                logger.warning("Bookys login round-trip failed: %s", e)
                self._login_error = f"site unreachable ({e})"
                return False

            if not _signed_in(answer.text):
                logger.warning(
                    "Bookys login failed — credentials wrong or site auth "
                    "changed (response status=%s)",
                    answer.status_code,
                )
                self._login_error = (
                    "login refused — check the username and password"
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
        assert self._client is not None

        try:
            resp = await self._client.get(
                f"{self.base_url}/search", params={"q": query}
            )
        except httpx.HTTPError as e:
            logger.warning("Bookys search failed for %r: %s", query, e)
            return []
        listing_urls = self._parse_listing_urls(resp.text)[:_SEARCH_LIMIT]
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
        """Release links of the search results table, in the
        site's order — the side columns list unrelated releases."""
        if not html_text:
            return []
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
    async def _get(self, url: str) -> str | None:
        assert self._client is not None
        async with self._fetch_slots:
            try:
                resp = await self._client.get(url)
            except httpx.HTTPError as e:
                logger.debug("Bookys fetch failed: %s (%s)", url, e)
                return None
        return resp.text if resp.status_code == 200 else None

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
        cover_url = self._first_text(
            tree,
            [
                "//meta[@name='og:image']/@content",
                "//meta[@property='og:image']/@content",
            ],
        )

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

        resolved = await asyncio.gather(
            *(self._resolve_dl(dl) for dl, _ in rows)
        )
        hosters: list[HosterLink] = []
        seen: set[str] = set()
        for link in resolved:
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
            cover_url=self._absolute(cover_url) if cover_url else None,
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
        if not self.username or not self.password:
            return False, "Bookys: credentials not configured"
        ok = await self._ensure_login()
        if not ok:
            return False, f"Bookys: {self._login_error}"
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


class _LoginForm:
    """The login form a Bookys page shows: where it posts and its
    one-shot ``_token``."""

    def __init__(self, action: str, token: str | None):
        self.action = action
        self.token = token


def _login_form(page_html: str, base_url: str) -> _LoginForm:
    """Read the ``username`` / ``password`` form of ``page_html``."""
    default = _LoginForm(f"{base_url}/login", None)
    if not page_html.strip():
        return default
    try:
        tree = html.fromstring(page_html)
    except (ValueError, etree.ParserError):
        return default
    for form in tree.xpath("//form"):
        names = set(form.xpath(".//input/@name"))
        if "username" in names and "password" in names:
            token = form.xpath(".//input[@name='_token']/@value")
            action = (form.get("action") or "").strip()
            if action and not action.startswith("http"):
                action = f"{base_url}/{action.lstrip('/')}"
            return _LoginForm(action or default.action, token[0] if token else None)
    return default


def _signed_in(page_html: str) -> bool:
    """A signed-in page offers a logout and no password field."""
    if not page_html.strip():
        return False
    try:
        tree = html.fromstring(page_html)
    except (ValueError, etree.ParserError):
        return False
    has_logout = bool(
        tree.xpath("//a[contains(@href,'logout')] | //form[contains(@action,'logout')]")
    )
    return has_logout and not tree.xpath("//input[@type='password']")


def _blocked(resp: httpx.Response) -> bool:
    """Cloudflare still challenging despite the clearance."""
    return resp.status_code == 403 and resp.headers.get("cf-mitigated") == "challenge"
