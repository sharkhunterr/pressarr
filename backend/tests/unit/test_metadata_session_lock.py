"""The cascade's providers share the request's session and run concurrently.

SQLAlchemy forbids concurrent operations on one session: without the lock, the
provider that lost the race dropped out of the search, and the request could 500.
"""

import asyncio

import pytest

from app.metadata.bnf import BnfProvider
from app.metadata.wikidata import WikidataProvider
from app.metadata.zdb import ZdbProvider


@pytest.mark.asyncio
async def test_providers_use_one_fresh_session_concurrently(test_session):
    providers = [WikidataProvider(db=test_session), BnfProvider(db=test_session), ZdbProvider(db=test_session)]

    await asyncio.gather(*(p._set_cache(f"k{i}", "{}") for i, p in enumerate(providers)))
    cached = await asyncio.gather(*(p._get_cache(f"k{i}") for i, p in enumerate(providers)))

    assert cached == ["{}", "{}", "{}"]


@pytest.mark.asyncio
async def test_a_provider_cancelled_mid_cache_write_leaves_the_session_usable(test_session):
    from sqlalchemy import text

    write = asyncio.ensure_future(ZdbProvider(db=test_session)._set_cache("k", "{}"))
    for _ in range(3):  # let the write reach the database thread
        await asyncio.sleep(0)
    write.cancel()
    with pytest.raises(asyncio.CancelledError):
        await write

    assert (await test_session.execute(text("select 1"))).scalar() == 1
    assert await WikidataProvider(db=test_session)._get_cache("k") is None
