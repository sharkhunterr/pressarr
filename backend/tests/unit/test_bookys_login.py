"""GitHub issue 1: Bookys moved to www7, a Laravel site behind Cloudflare.

Every page goes through one FlareSolverr session (a real browser tab); no account is
needed. FlareSolverr is simulated here with pages shaped like the real ones: what is
checked is what Pressarr asks for and what it reads back.
"""

import pytest

from app.indexers.magazine_scene.bookys import BookysIndexer
from app.services.flaresolverr import FlareSolverrError

BASE = "https://www7.bookys-ebooks.com"

SEARCH = f"""<html><body>
<div class="sidebar"><a href="/journaux/1-le-monde-du-lundi-2-novembre-2026">top</a></div>
<table id="search_table"><tr><th>Titre</th><th>Catégorie</th></tr>
<tr><td><a href="{BASE}/journaux/358434-le-monde-du-samedi-7-novembre-2026">Le Monde</a></td></tr>
<tr><td><a href="/tutos-logiciels/357927-android-le-monde-v927-premium-apk">[ANDROID] Le Monde</a></td></tr>
</table></body></html>"""

RELEASE = f"""<html><head>
<meta name="og:image" content="{BASE}/storage/items/le-monde.jpg"></head><body>
<h1>Le Monde Du Samedi 7 Novembre 2026</h1>
<table><tr><th>Type</th><th>Format</th><th>Langue</th><th>Taille</th><th>Part</th></tr>
<tr><td><a class="bys-host" href="{BASE}/journaux/358434-le-monde/dl/1">Nitroflare</a></td>
<td>PDF</td><td>Français</td><td>32 MB</td><td>Complète</td></tr>
<tr><td><a class="bys-host" href="{BASE}/journaux/358434-le-monde/dl/2">Fileroy.com</a></td>
<td>PDF</td><td>Français</td><td>32 MB</td><td>Complète</td></tr>
</table></body></html>"""

PAGES = {
    "/search?q=Le%20Monde": SEARCH,
    "/search?q=le": SEARCH,
    "/journaux/358434-le-monde-du-samedi-7-novembre-2026": RELEASE,
    "/journaux/358434-le-monde/dl/1": "<a href='https://nitroflare.com/view/D0C7532'>go</a>",
    "/journaux/358434-le-monde/dl/2": "<p>https://fileroy.com/0Pdzy/file</p>",
}


class FakeFlare:
    """FlareSolverr serving the Bookys pages in one session."""

    def __init__(self):
        self.gets: list[tuple[str, str | None]] = []
        self.destroyed: list[str] = []

    async def create_session(self, name):
        return name

    async def destroy_session(self, name):
        self.destroyed.append(name)

    async def close(self):
        pass

    async def request_get(self, url, session=None):
        self.gets.append((url, session))
        page = PAGES.get(url.removeprefix(BASE))
        return {"status": 200 if page else 404, "response": page or "Not found"}


class StuckFlare(FakeFlare):
    """FlareSolverr that cannot solve the site's Cloudflare challenge."""

    async def request_get(self, url, session=None):
        raise FlareSolverrError("Error solving the challenge. Timeout after 120.0 seconds.")


def indexer(flare) -> BookysIndexer:
    return BookysIndexer(base_url=BASE, username="", password="", flaresolverr=flare)


@pytest.mark.asyncio
async def test_a_search_reads_the_results_table_and_resolves_each_hoster_link():
    flare = FakeFlare()
    idx = indexer(flare)
    releases = await idx.search("Le Monde")
    await idx.close()

    assert len(releases) == 1  # the sidebar and the APK are left out
    r = releases[0]
    assert r.source_url == f"{BASE}/journaux/358434-le-monde-du-samedi-7-novembre-2026"
    assert r.title == "Le Monde Du Samedi 7 Novembre 2026"
    assert [(h.hoster, h.url) for h in r.hoster_links] == [
        ("nitroflare.com", "https://nitroflare.com/view/D0C7532"),
        ("fileroy.com", "https://fileroy.com/0Pdzy/file"),
    ]
    assert (r.file_format, r.language, r.size_bytes) == ("pdf", "fr", 32 * 1024 * 1024)
    # Bookys covers answer 403 to a browser without the clearance.
    assert r.cover_url is None
    # One browser tab for the whole scrape, closed afterwards.
    assert {s for _, s in flare.gets} == set(flare.destroyed) and len(flare.destroyed) == 1


@pytest.mark.asyncio
async def test_a_release_found_by_two_queries_is_fetched_once():
    flare = FakeFlare()
    idx = indexer(flare)
    await idx.search("Le Monde")
    first = len(flare.gets)
    again = await idx.search("Le Monde")
    await idx.close()

    assert len(again) == 1
    assert len(flare.gets) == first + 1  # only the search page


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
    assert await idx.test_connection() == (False, "Bookys: FlareSolverr endpoint not configured")
