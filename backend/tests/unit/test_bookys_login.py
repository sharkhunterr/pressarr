"""GitHub issue 1: Bookys moved to www7, a Laravel site.

FlareSolverr only solves the Cloudflare challenge; the login (``_token`` / ``username`` /
``password`` posted to ``/login``), the search (``/search?q=``) and the release pages go
through httpx with the clearance. Both are simulated here: what is checked is what
Pressarr sends and what it reads back from pages shaped like the real ones.
"""

from urllib.parse import parse_qs

import httpx
import pytest

from app.indexers.magazine_scene.bookys import BookysIndexer
from app.services.flaresolverr import FlareSolverrError

BASE = "https://www7.bookys-ebooks.com"

LOGIN_PAGE = f"""<html><body>
<form method="POST" action="{BASE}/login">
  <input type="hidden" name="_token" value="tok-123">
  <input type="text" name="username"><input id="password" type="password" name="password">
  <input type="checkbox" name="remember"><button type="submit">Connexion</button>
</form></body></html>"""

REFUSED = LOGIN_PAGE.replace(
    "<form", "<p>Aucun utilisateur trouvé pour les identifiants fournis</p><form"
)

SIGNED_IN = f"<html><body><a href='{BASE}/logout'>Déconnexion</a></body></html>"

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

DL = {
    "/journaux/358434-le-monde/dl/1": "<a href='https://nitroflare.com/view/D0C7532'>go</a>",
    "/journaux/358434-le-monde/dl/2": "<p>https://fileroy.com/0Pdzy/file</p>",
}


class FakeFlare:
    """FlareSolverr handing back a clearance cookie and its User-Agent."""

    def __init__(self):
        self.closed = False

    async def request_get(self, url, session=None):
        return {
            "status": 200,
            "userAgent": "UA/1.0",
            "cookies": [{"name": "cf_clearance", "value": "clear"}],
        }

    async def close(self):
        self.closed = True


class StuckFlare(FakeFlare):
    """FlareSolverr that cannot solve the site's Cloudflare challenge."""

    async def request_get(self, url, session=None):
        raise FlareSolverrError("Error solving the challenge. Timeout after 120.0 seconds.")


class FakeSite:
    """The Bookys pages, served to httpx."""

    def __init__(self, login_answer: str):
        self.login_answer = login_answer
        self.posts: list[tuple[str, dict, httpx.Headers]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/login":
            self.posts.append((path, parse_qs(request.content.decode()), request.headers))
            return httpx.Response(200, text=self.login_answer)
        if path == "/login":
            return httpx.Response(200, text=LOGIN_PAGE)
        if path == "/search":
            return httpx.Response(200, text=SEARCH)
        if path in DL:
            return httpx.Response(200, text=DL[path])
        if path.startswith("/journaux/358434"):
            return httpx.Response(200, text=RELEASE)
        return httpx.Response(404)


@pytest.fixture
def indexer(monkeypatch):
    """A Bookys indexer whose httpx client talks to ``site``."""

    def make(site: FakeSite, flare=None) -> BookysIndexer:
        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kw: real_client(transport=httpx.MockTransport(site.handler), **kw),
        )
        return BookysIndexer(
            base_url=BASE, username="me@x", password="p&ss*", flaresolverr=flare or FakeFlare()
        )

    return make


@pytest.mark.asyncio
async def test_the_login_posts_the_token_and_the_credentials_with_the_clearance(indexer):
    site = FakeSite(SIGNED_IN)
    idx = indexer(site)
    assert await idx._ensure_login() is True
    path, data, headers = site.posts[0]
    assert data == {
        "_token": ["tok-123"],
        "username": ["me@x"],
        "password": ["p&ss*"],
        "remember": ["on"],
    }
    assert headers["user-agent"] == "UA/1.0"
    assert "cf_clearance=clear" in headers["cookie"]
    await idx.close()


@pytest.mark.asyncio
async def test_the_connection_test_says_when_the_credentials_are_refused(indexer):
    ok, message = await indexer(FakeSite(REFUSED)).test_connection()
    assert ok is False
    assert "refused" in message and "password" in message


@pytest.mark.asyncio
async def test_a_page_expired_answer_is_not_a_login(indexer):
    page_expired = "<html><head><title>Page Expired</title></head><body>419</body></html>"
    assert await indexer(FakeSite(page_expired))._ensure_login() is False


@pytest.mark.asyncio
async def test_the_connection_test_names_a_cloudflare_failure_not_a_refused_login(indexer):
    ok, message = await indexer(FakeSite(SIGNED_IN), StuckFlare()).test_connection()
    assert ok is False
    assert "protection" in message and "solving the challenge" in message
    assert "refused" not in message


@pytest.mark.asyncio
async def test_a_search_reads_the_results_table_and_resolves_each_hoster_link(indexer):
    idx = indexer(FakeSite(SIGNED_IN))
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
    assert r.cover_url == f"{BASE}/storage/items/le-monde.jpg"
