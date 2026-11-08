"""GitHub issue 1: Bookys moved to www7, a Laravel site behind Cloudflare.

Every page goes through one FlareSolverr session (a real browser tab) shared by
every scan and kept open between them; no account is needed. FlareSolverr is
simulated here with pages shaped like the real ones: what is checked is what
Pressarr asks for and what it reads back.
"""

from datetime import date

import pytest

from app.indexers.magazine_scene.bookys import (
    BookysIndexer,
    _guess_frequency,
    _title_stem,
)
from app.services.flaresolverr import FlareSolverrError

BASE = "https://www7.bookys-ebooks.com"


def row(title, path, section, category=None):
    """One line of the search results table, as the site writes it."""
    cat = f' / <a href="{BASE}/{section}/{category[1]}">{category[0]}</a>' if category else ""
    return f"""<tr>
<td><span>Titre:</span><a href="{BASE}{path}" class="bys-link">{title}</a></td>
<td><span>Catégorie:</span> <a href="{BASE}/{section}/new">{section.title()}</a>{cat}</td>
<td><span>Vues:</span> <span class="live_views">2029</span></td></tr>"""


SEARCH = f"""<html><body>
<div class="sidebar"><a href="/journaux/1-le-monde-du-lundi-2-novembre-2026">top</a></div>
<table id="search_table"><tr><th>Titre</th><th>Catégorie</th><th>Vues</th></tr>
{row("Le Monde Du Samedi 7 Novembre 2026", "/journaux/358434-le-monde-du-samedi-7-novembre-2026", "journaux", ("Le Monde", "le-monde"))}
{row("Le Monde du Vendredi 6 Novembre 2026", "/journaux/358293-le-monde-du-vendredi-6-novembre-2026", "journaux", ("Le Monde", "le-monde"))}
{row("Le Monde du Jeudi 5 Novembre 2026", "/journaux/358081-le-monde-du-jeudi-5-novembre-2026", "journaux", ("Le Monde", "le-monde"))}
{row("Le Monde des Ados - 4 Novembre 2026", "/magazines/357979-le-monde-des-ados-4-novembre-2026", "magazines", ("Jeunesse", "jeunesse"))}
{row("[ANDROID] Le Monde v9.27 (Premium) [APK]", "/tutos-logiciels/357927-android-le-monde-v927-premium-apk", "tutos-logiciels", ("Logiciel", "logiciel"))}
{row("Le français dans le monde - Novembre-Décembre 2026", "/magazines/357549-le-francais-dans-le-monde-novembre-decembre-2026", "magazines", ("Culture", "culture"))}
</table></body></html>"""


def release(title, published, abstract, dl_ids):
    rows = "".join(
        f"""<tr><td><a class="bys-host" href="{BASE}/journaux/358434-le-monde/dl/{i}">Host</a></td>
<td>PDF</td><td>Français</td><td>32 MB</td><td>Complète</td></tr>"""
        for i in dl_ids
    )
    return f"""<html><head>
<meta name="og:image" content="{BASE}/storage/items/le-monde.jpg"></head><body>
<h1>{title}</h1>
<ul><li><b>Date de sortie</b>: 06-11-2026
<span class="hidden" itemprop="datePublished">
   {published}
</span></li></ul>
<p itemprop="abstract">{abstract}</p>
<table><tr><th>Type</th><th>Format</th><th>Langue</th><th>Taille</th><th>Part</th></tr>
{rows}</table></body></html>"""


MONDE = "Le Monde - 1er site d'information."
PAGES = {
    "/search?q=Le%20Monde": SEARCH,
    "/search?q=le": SEARCH,
    "/journaux/358434-le-monde-du-samedi-7-novembre-2026": release(
        "Le Monde Du Samedi 7 Novembre 2026", "2026-11-07", MONDE, [1, 2]
    ),
    "/journaux/358293-le-monde-du-vendredi-6-novembre-2026": release(
        "Le Monde du Vendredi 6 Novembre 2026", "2026-11-06", MONDE, [1]
    ),
    "/journaux/358081-le-monde-du-jeudi-5-novembre-2026": release(
        "Le Monde du Jeudi 5 Novembre 2026", "2026-11-05", MONDE, [1]
    ),
    "/magazines/357979-le-monde-des-ados-4-novembre-2026": release(
        "Le Monde des Ados - 4 Novembre 2026", "2026-11-04", "Pour les ados", [2]
    ),
    "/journaux/358434-le-monde/dl/1": "<a href='https://nitroflare.com/view/D0C7532'>go</a>",
    "/journaux/358434-le-monde/dl/2": "<p>https://fileroy.com/0Pdzy/file?af=1&amp;dl=2</p>",
}


class FakeFlare:
    """FlareSolverr serving the Bookys pages."""

    def __init__(self):
        self.gets: list[tuple[str, str | None]] = []
        self.destroyed: list[str] = []

    async def destroy_session(self, name):
        self.destroyed.append(name)

    async def close(self):
        pass

    async def request_get(self, url, session=None, session_ttl_minutes=None):
        self.gets.append((url.removeprefix(BASE), session))
        page = PAGES.get(url.removeprefix(BASE))
        return {"status": 200 if page else 404, "response": page or "Not found"}


class StuckFlare(FakeFlare):
    """FlareSolverr that cannot solve the site's Cloudflare challenge."""

    async def request_get(self, url, session=None, session_ttl_minutes=None):
        raise FlareSolverrError("Error solving the challenge. Timeout after 120.0 seconds.")


def indexer(flare) -> BookysIndexer:
    return BookysIndexer(base_url=BASE, username="", password="", flaresolverr=flare)


@pytest.mark.asyncio
async def test_a_search_reads_the_results_table_and_resolves_each_hoster_link():
    flare = FakeFlare()
    idx = indexer(flare)
    releases = await idx.search("Le Monde")
    await idx.close()

    # The sidebar, the APK and "Le français dans le monde" are left out;
    # "Le Monde des Ados" is close enough to be looked at (the scan
    # applies the magazine's own threshold).
    assert [r.title for r in releases] == [
        "Le Monde Du Samedi 7 Novembre 2026",
        "Le Monde du Vendredi 6 Novembre 2026",
        "Le Monde du Jeudi 5 Novembre 2026",
        "Le Monde des Ados - 4 Novembre 2026",
    ]
    assert not any("francais" in url or "apk" in url for url, _ in flare.gets)
    r = releases[0]
    assert r.source_url == f"{BASE}/journaux/358434-le-monde-du-samedi-7-novembre-2026"
    assert [(h.hoster, h.url) for h in r.hoster_links] == [
        ("nitroflare.com", "https://nitroflare.com/view/D0C7532"),
        ("fileroy.com", "https://fileroy.com/0Pdzy/file?af=1&dl=2"),
    ]
    assert (r.file_format, r.language, r.size_bytes) == ("pdf", "fr", 32 * 1024 * 1024)
    assert r.published_at == "2026-11-07"
    # Bookys covers answer 403 to a browser without the clearance.
    assert r.cover_url is None
    # One browser tab for every page, left open for the next scan.
    assert len({s for _, s in flare.gets}) == 1 and flare.destroyed == []


@pytest.mark.asyncio
async def test_a_release_found_by_two_queries_is_fetched_once():
    flare = FakeFlare()
    idx = indexer(flare)
    await idx.search("Le Monde")
    first = len(flare.gets)
    again = await idx.search("Le Monde")
    await idx.close()

    assert len(again) == 4
    assert len(flare.gets) == first + 1  # only the search page


@pytest.mark.asyncio
async def test_a_title_search_lists_each_title_once_with_what_its_issues_tell():
    flare = FakeFlare()
    titles = await indexer(flare).search_titles("Le Monde")

    # Every title holding all the words searched for, that very title first.
    monde, ados, francais = titles
    assert (monde.title, monde.kind, monde.genre) == ("Le Monde", "newspaper", None)
    assert monde.url == f"{BASE}/journaux/le-monde"
    assert (monde.issue_count, monde.latest_date, monde.frequency) == (3, "2026-11-07", "daily")
    assert (monde.description, monde.language) == (MONDE, "fr")
    assert (ados.title, ados.kind, ados.genre) == ("Le Monde des Ados", "magazine", "Jeunesse")
    assert ados.description == "Pour les ados"
    assert francais.title == "Le français dans le monde"
    # Only the search page and one page per title (that one is missing).
    assert len(flare.gets) == 4


@pytest.mark.parametrize(
    ("issue", "title"),
    [
        ("Le Monde Du Samedi 7 Novembre 2026", "Le Monde"),
        ("Le Monde des Ados - 4 Novembre 2026", "Le Monde des Ados"),
        ("Le français dans le monde - Novembre-Décembre 2026", "Le français dans le monde"),
        ("Le Monde Magazine du Samedi 31 octobre 2026", "Le Monde Magazine"),
        ("L'Équipe Magazine Spécial - 24 Août 2024", "L'Équipe Magazine"),
        ("Picsou Magazine N°612 - Novembre 2026", "Picsou Magazine"),
        ("Super Picsou Géant N.238 - Octobre-Novembre 2023", "Super Picsou Géant"),
        ("Science & Vie Hors-Série - Automne 2026", "Science & Vie"),
        ("Société Civile - Été 2026", "Société Civile"),
    ],
)
def test_an_issue_title_loses_its_date_and_number(issue, title):
    assert _title_stem(issue) == title


def test_the_frequency_is_the_usual_gap_between_issues():
    def days(*ds):
        return [date(2026, m, d) for m, d in ds]

    assert _guess_frequency(days((11, 7), (11, 6), (11, 5), (11, 3))) == "daily"
    assert _guess_frequency(days((10, 1), (10, 15), (10, 29))) == "biweekly"
    assert _guess_frequency(days((7, 1), (9, 1), (11, 1))) == "bimonthly"
    assert _guess_frequency(days((10, 1), (11, 1))) is None  # too few to tell


@pytest.mark.asyncio
async def test_the_connection_test_needs_no_account():
    ok, message = await indexer(FakeFlare()).test_connection()
    assert ok is True and "no account" in message


@pytest.mark.asyncio
async def test_the_connection_test_names_a_cloudflare_failure():
    ok, message = await indexer(StuckFlare()).test_connection()
    assert ok is False
    assert "protection" in message and "solving the challenge" in message


@pytest.mark.asyncio
async def test_without_flaresolverr_there_is_nothing_to_search():
    idx = indexer(None)
    assert await idx.search("Le Monde") == []
    assert await idx.search_titles("Le Monde") == []
    assert await idx.test_connection() == (False, "Bookys: FlareSolverr endpoint not configured")
