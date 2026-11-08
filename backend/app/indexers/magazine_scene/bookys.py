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
time, which also keeps the site from answering 429. The tab is
shared by every scan and lookup and outlives them: only the
first request after a restart pays for the challenge.

No account is needed: the search, the release pages and their
``/dl/`` pages are public. (Signing in could not work through
FlareSolverr anyway: its ``request.post`` submits from a
``data:`` page, the browser withholds the SameSite session
cookie and Laravel answers "Page Expired".) The username and
password stay in the settings but are not used.

Flow:

1. ``GET /search?q=…`` → the ``#search_table`` rows (Titre,
   Catégorie, Vues); only the ``/journaux/`` and
   ``/magazines/`` entries are kept. A newspaper's category is
   its own title ("Journaux / Le Monde"), a magazine's is a
   genre ("Magazines / Jeunesse").
2. ``GET`` each release page → its release date, its abstract
   and its download table (Type, Format, Langue, Taille, Part),
   one ``…/dl/<id>`` link per hoster; each ``/dl/`` page holds
   the real hoster URL.

``search_titles`` stops after step 1 to list the titles a
search turns up, for the add-magazine page.

When no FlareSolverr endpoint is configured, the scraper returns
``[]`` — pressarr keeps working with ``telecharger_magazines``
only.
"""

import asyncio
import html as html_entities
import logging
import re
import unicodedata
import weakref
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from urllib.parse import quote, urlsplit

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
from app.parser.magazine_parser import parse_magazine_filename
from app.services.flaresolverr import (
    FlareSolverrClient,
    FlareSolverrError,
)
from app.services.title_match import content_tokens, title_match_score

logger = logging.getLogger(__name__)


# Release pages worth a look: /journaux/<id>-<slug> and
# /magazines/<id>-<slug> (books, comics and software share the
# search but are not Pressarr's business).
_RELEASE_RE = re.compile(r"/(?:journaux|magazines)/\d+-[\w-]+/?$")
_DL_RE = re.compile(r"/dl/\d+/?$")
_URL_RE = re.compile(r"""https?://[^\s"'<>]+""")
_SEARCH_LIMIT = 8
_LANGUAGES = {"français": "fr", "francais": "fr", "anglais": "en"}
# A search row scoring below this against the query is not the
# title searched for ("Le français dans le monde" for "Le Monde"):
# its pages are not worth fetching. The scan then applies the
# magazine's own threshold.
_ROW_MATCH = 50.0
_TITLES_LIMIT = 5

# FlareSolverr creates a session on its first request and keeps it
# until destroyed; past this age it swaps the tab for a fresh one.
_SESSION = "pressarr-bookys"
_SESSION_TTL_MINUTES = 360

# One request at a time in the shared tab, whichever indexer
# instance sends it.
_tab_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = (
    weakref.WeakKeyDictionary()
)


def _tab_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _tab_locks.get(loop)
    if lock is None:
        lock = _tab_locks[loop] = asyncio.Lock()
    return lock


@dataclass
class _Row:
    """One line of the search results table."""

    title: str
    url: str
    section: str  # "journaux" | "magazines"
    category: str | None  # newspaper title or magazine genre
    category_url: str | None


@dataclass
class BookysTitle:
    """A title a Bookys search turns up, with what its issues
    tell about it."""

    title: str
    url: str
    kind: str  # "newspaper" | "magazine"
    genre: str | None
    issue_count: int
    latest_issue: str
    latest_date: str | None
    frequency: str | None
    language: str | None = None
    description: str | None = None


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
        # A scan searches the title and its aliases: the same
        # release pages come back, fetch them once.
        self._releases: dict[str, MagazineSceneRelease | None] = {}
        # Why the last page could not be fetched, for the connection test.
        self._error = "site unreachable"

    async def close(self) -> None:
        # The shared tab stays open for the next scan.
        if self._flare:
            await self._flare.close()

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    async def _get(self, url: str) -> str | None:
        """The page's HTML, or ``None`` (reason in ``_error``)."""
        if self._flare is None:
            self._error = "FlareSolverr endpoint not configured"
            return None
        async with _tab_lock():
            try:
                sol = await self._flare.request_get(
                    url,
                    session=_SESSION,
                    session_ttl_minutes=_SESSION_TTL_MINUTES,
                )
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
        rows = await self._search_rows(query)
        listing_urls = [
            r.url for r in rows if title_match_score(r.title, query) >= _ROW_MATCH
        ][:_SEARCH_LIMIT]
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

    async def _search_rows(self, query: str) -> list["_Row"]:
        page = await self._get(f"{self.base_url}/search?q={quote(query)}")
        if page is None:
            logger.warning("Bookys search failed for %r: %s", query, self._error)
            return []
        return self._parse_rows(page)

    def _parse_rows(self, html_text: str) -> list[_Row]:
        """Newspaper and magazine rows of the search results
        table, in the site's order — the side columns list
        unrelated releases."""
        try:
            tree = html.fromstring(html_text)
        except (ValueError, etree.ParserError):
            return []
        out: list[_Row] = []
        seen: set[str] = set()
        for tr in tree.xpath("//table[@id='search_table']//tr[td]"):
            cells = tr.xpath("./td")
            links = cells[0].xpath(".//a[@href]")
            if not links:
                continue
            url = self._absolute(links[0].get("href"))
            if not url or not _RELEASE_RE.search(url) or url in seen:
                continue
            seen.add(url)
            # "Journaux / Le Monde": the section, then the category.
            cat_links = cells[1].xpath(".//a[@href]") if len(cells) > 1 else []
            category = cat_links[1] if len(cat_links) > 1 else None
            out.append(
                _Row(
                    title=" ".join(links[0].text_content().split()),
                    url=url,
                    section=urlsplit(url).path.strip("/").split("/")[0],
                    category=(
                        " ".join(category.text_content().split()) or None
                        if category is not None
                        else None
                    ),
                    category_url=(
                        self._absolute(category.get("href"))
                        if category is not None
                        else None
                    ),
                )
            )
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
        published = self._first_text(tree, ["//*[@itemprop='datePublished']"])

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
            published_at=published,
            # The site's covers (/storage/items/…) answer 403 without
            # the Cloudflare clearance: a browser would show them broken.
            cover_url=None,
        )

    async def _resolve_dl(self, dl_url: str) -> HosterLink | None:
        """The hoster URL a ``…/dl/<id>`` page hands out."""
        body = await self._get(dl_url)
        if not body:
            return None
        for found in _URL_RE.findall(body):
            # Read from the raw HTML: "&amp;" stands for "&".
            url = html_entities.unescape(found)
            hoster = detect_hoster(url)
            if hoster:
                return HosterLink(hoster=hoster, url=url)
        return None

    # ------------------------------------------------------------------
    # Titles (add-magazine page)
    # ------------------------------------------------------------------
    async def search_titles(self, query: str) -> list[BookysTitle]:
        """The newspapers and magazines a search turns up, one per
        title, each described from its issues in the results and
        from the page of its latest one."""
        wanted = content_tokens(query)
        if not wanted:
            return []
        groups: dict[str, list[_Row]] = {}
        for row in await self._search_rows(query):
            name = self._title_of(row)
            if wanted <= content_tokens(name):
                key = row.category_url if self._is_newspaper(row) else _fold(name)
                groups.setdefault(key or row.url, []).append(row)

        titles: list[tuple[BookysTitle, str]] = []
        for rows in groups.values():
            dated = sorted(
                ((_issue_date(r.title), r) for r in rows),
                key=lambda d: d[0] or date.min,
                reverse=True,
            )
            latest_date, latest = dated[0]
            newspaper = self._is_newspaper(latest)
            titles.append((
                BookysTitle(
                    title=self._title_of(latest),
                    url=(latest.category_url if newspaper else None) or latest.url,
                    kind="newspaper" if newspaper else "magazine",
                    genre=None if newspaper else latest.category,
                    issue_count=len(rows),
                    latest_issue=latest.title,
                    latest_date=latest_date.isoformat() if latest_date else None,
                    frequency=_guess_frequency([d for d, _ in dated if d]),
                ),
                latest.url,
            ))
        # The title searched for first, then the most published.
        titles.sort(
            key=lambda t: (content_tokens(t[0].title) != wanted, -t[0].issue_count)
        )
        titles = titles[:_TITLES_LIMIT]

        # The latest issue's page describes the title.
        for t, latest_url in titles:
            body = await self._get(latest_url)
            if not body:
                continue
            try:
                tree = html.fromstring(body)
            except (ValueError, etree.ParserError):
                continue
            t.description = self._first_text(tree, ["//*[@itemprop='abstract']"])
            language = self._first_text(
                tree, ["//a[contains(@href, '/dl/')]/ancestor::tr[1]/td[3]"]
            )
            if language:
                t.language = _LANGUAGES.get(language.lower(), language.lower()[:5])
        return [t for t, _ in titles]

    @staticmethod
    def _is_newspaper(row: _Row) -> bool:
        return row.section == "journaux" and bool(row.category)

    @staticmethod
    def _title_of(row: _Row) -> str:
        """A newspaper's category is its title; a magazine's title
        is its issue's, without the date or the number."""
        if BookysIndexer._is_newspaper(row):
            return row.category or row.title
        return _title_stem(row.title)

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


# ----------------------------------------------------------------------
# Titles
# ----------------------------------------------------------------------
_MONTHS = (
    "janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre"
    "|octobre|novembre|decembre"
)
_DAYS = "lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche"
# Where an issue title stops naming the title: its day, date,
# number, season or special-issue marker.
_ISSUE_PART = re.compile(
    r"[\s\-–:|,]*(?:\b(?:du|de|des)\s+)?\b(?:"
    rf"{_DAYS}|{_MONTHS}|\d{{1,2}}(?:er)?\s+(?:{_MONTHS})"
    r"|n[°o.]\s*\d+|hors[- ]serie|speciale?|(?:19|20)\d{2}"
    r"|printemps|ete|automne|hiver)\b"
)


def _fold(text: str) -> str:
    """Lower case without accents, one character per character so
    positions still match the original."""
    return "".join(unicodedata.normalize("NFKD", c)[0] for c in text).lower()


def _title_stem(issue_title: str) -> str:
    m = _ISSUE_PART.search(_fold(issue_title))
    if m is None or m.start() == 0:
        return issue_title.strip()
    return issue_title[: m.start()].strip(" -–:|,")


def _issue_date(issue_title: str) -> date | None:
    p = parse_magazine_filename(issue_title)
    if not (p.year and p.month):
        return None
    try:
        return date(p.year, p.month, p.day or 1)
    except ValueError:
        return None


# Median days between two issues → frequency, as the add form names it.
_FREQUENCIES = (
    (2, "daily"),
    (10, "weekly"),
    (20, "biweekly"),
    (45, "monthly"),
    (75, "bimonthly"),
    (120, "quarterly"),
    (240, "semiannual"),
    (500, "annual"),
)


def _guess_frequency(dates: list[date]) -> str | None:
    days = sorted(set(dates))
    if len(days) < 3:
        return None
    gaps = sorted((b - a).days for a, b in zip(days, days[1:]))
    median = gaps[len(gaps) // 2]
    return next((f for limit, f in _FREQUENCIES if median <= limit), "irregular")
