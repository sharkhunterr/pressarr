"""GitHub issue 1: Bookys moved to www7 and replaced its login form.

The new form posts ``_token`` / ``username`` / ``password`` to ``/index.php/login``;
the old DataLife Engine form (``login_name``, ``dle_user_id`` cookie) is still understood.
The FlareSolverr round-trips are simulated: what is checked is what Pressarr sends.
"""

import pytest

from app.indexers.magazine_scene.bookys import BookysIndexer

BASE = "https://www7.bookys-ebooks.com"

NEW_FORM = f"""<html><body>
<form method="POST" action="{BASE}/index.php/login">
  <input name="_token" type="hidden" value="tok-123">
  <input name="username" type="text">
  <input name="password" type="password">
  <input name="remember" type="checkbox">
  <button type="submit">Connexion</button>
</form></body></html>"""

OLD_FORM = """<html><body><form method="post">
  <input name="login_name" type="text"><input name="login_password" type="password">
</form></body></html>"""

SIGNED_IN = "<html><body><a href='/index.php/logout'>Déconnexion</a></body></html>"


class FakeFlare:
    def __init__(self, page: str, answer: dict):
        self.page, self.answer, self.posts = page, answer, []

    async def create_session(self, name):
        return "s1"

    async def request_get(self, url, session=None):
        return {"status": 200, "response": self.page, "cookies": []}

    async def request_post(self, url, post_data=None, session=None):
        self.posts.append((url, post_data))
        return self.answer


def indexer(flare):
    return BookysIndexer(base_url=BASE, username="me@x", password="p&ss", flaresolverr=flare)


@pytest.mark.asyncio
async def test_the_new_form_posts_its_token_and_the_credentials():
    flare = FakeFlare(NEW_FORM, {"status": 200, "response": SIGNED_IN, "cookies": []})
    assert await indexer(flare)._ensure_login() is True
    url, data = flare.posts[0]
    assert url == f"{BASE}/index.php/login"
    assert "_token=tok-123" in data and "username=me%40x" in data and "password=p%26ss" in data


@pytest.mark.asyncio
async def test_the_new_form_answering_with_the_form_again_is_a_failed_login():
    flare = FakeFlare(NEW_FORM, {"status": 200, "response": NEW_FORM, "cookies": []})
    assert await indexer(flare)._ensure_login() is False


@pytest.mark.asyncio
async def test_the_old_dle_form_still_signs_in_with_its_cookie():
    answer = {"status": 200, "response": SIGNED_IN, "cookies": [{"name": "dle_user_id", "value": "9"}]}
    flare = FakeFlare(OLD_FORM, answer)
    assert await indexer(flare)._ensure_login() is True
    url, data = flare.posts[0]
    assert url == f"{BASE}/index.php?do=login" and "login_name=me%40x" in data
