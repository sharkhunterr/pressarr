"""Serialise the metadata caches' use of a shared session.

The cascade runs its providers concurrently (ZDB, Wikidata, BnF,
ISSN Portal, Google Books…) and they all read and write their
``metadata_cache`` rows through the request's ``AsyncSession``.
SQLAlchemy forbids concurrent operations on one session ("This
session is provisioning a new connection; concurrent operations
are not permitted"): the provider that lost the race dropped out
of the results, and the request could end in a 500. The network
calls stay concurrent; only the short cache round-trips queue.
"""

import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

_LOCK_KEY = "pressarr_metadata_lock"


def session_lock(db: AsyncSession) -> asyncio.Lock:
    """The lock every metadata cache takes before using ``db``."""
    lock = db.info.get(_LOCK_KEY)
    if lock is None:
        lock = db.info[_LOCK_KEY] = asyncio.Lock()
    return lock


def serialized[T](
    method: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]:
    """Run a provider's cache method under its session's lock."""

    @functools.wraps(method)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
        if self.db is None:
            return await method(self, *args, **kwargs)
        async with session_lock(self.db):
            task = asyncio.ensure_future(method(self, *args, **kwargs))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                # The cascade cancels a slow provider. Cut mid-flush, the
                # round-trip would leave the session's connection closed for
                # the rest of the request: finish it, then honour the cancel.
                await asyncio.wait({task})
                if not task.cancelled():
                    task.exception()  # retrieved: nobody else awaits it
                raise

    return wrapper
