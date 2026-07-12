"""Cover-image fallback via the scene magazine indexers.

The regular cascade (ZDB / Wikidata / BnF / ISSN Portal / Google
Books) already returns a cover when one of those upstream
catalogues has registered it. The trade-off: niche FR titles
and most dailies only get a logo (Wikidata P154) or nothing at
all.

The scene scrapers we ship — Bookys + telecharger-magazines.org
— happen to surface the actual current-issue cover on every
article page (``og:image``). This module exposes
``find_scene_cover(query, config, db)`` which:

- Hits the indexers in parallel (FlareSolverr-routed Bookys,
  plain httpx tm.org) using the cheap "search + take the
  newest release" path.
- Returns the first non-empty cover URL.
- Caches the answer in ``metadata_cache`` for 24h so a hot
  search (Picsou Magazine, L'Équipe, …) costs one scrape per
  day max.

Returns ``None`` when no indexer is enabled, no scrape returns
a cover, or every indexer raised — callers fall back to the
no-cover render path they already had.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.indexers.magazine_scene.base import MagazineSceneIndexerBase
from app.models.metadata_cache import MetadataCache
from app.services.magazine_release_service import build_enabled_indexers

logger = logging.getLogger(__name__)

_CACHE_PROVIDER = "scene_cover"
_CACHE_TTL = timedelta(hours=24)


async def find_scene_cover(
    query: str,
    config,
    db: AsyncSession | None = None,
) -> str | None:
    """Return the first scene-indexer cover URL for ``query`` or
    ``None``. ``db`` is optional; when passed, results are
    cached in ``metadata_cache``. Scrape happens even without
    db (caller usually passes one)."""
    q = (query or "").strip()
    if not q:
        return None

    indexers = build_enabled_indexers(config)
    if not indexers:
        return None

    # Cache lookup first — keep the scrape budget bounded.
    if db is not None:
        cached = await _cache_get(db, q)
        if cached is not None:
            return cached or None  # empty string sentinel = no-cover

    # Race every enabled indexer; first one with a hit wins.
    # Each indexer returns multiple releases — we just want the
    # cover of the freshest one, so take ``releases[0]``.
    cover = await _race_cover(indexers, q)

    # Politely shut every scraper's httpx client down so we don't
    # leak connections (Bookys keeps a FlareSolverr session live
    # until close()).
    for indexer in indexers:
        try:
            await indexer.close()  # type: ignore[attr-defined]
        except Exception:
            pass

    if db is not None:
        await _cache_put(db, q, cover or "")

    return cover or None


async def _race_cover(
    indexers: list[MagazineSceneIndexerBase], query: str
) -> str | None:
    """First indexer to return a release with a cover wins.
    Wraps each scrape in a Task so ``asyncio.as_completed`` can
    race them; cancels the losers as soon as we have an answer."""

    async def one(indexer: MagazineSceneIndexerBase) -> str | None:
        try:
            releases = await indexer.search(query)
        except Exception:
            logger.debug(
                "Scene cover scrape failed for %s / %r",
                indexer.name, query, exc_info=True,
            )
            return None
        for r in releases:
            if r.cover_url:
                return r.cover_url
        return None

    tasks = [asyncio.create_task(one(i)) for i in indexers]
    try:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                return result
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
    return None


# ----------------------------------------------------------------------
# Cache plumbing
# ----------------------------------------------------------------------


async def _cache_get(db: AsyncSession, query: str) -> str | None:
    row = await db.scalar(
        select(MetadataCache).where(
            MetadataCache.provider == _CACHE_PROVIDER,
            MetadataCache.cache_key == query.lower(),
        )
    )
    if row is None:
        return None
    if row.expires_at and row.expires_at < datetime.utcnow():
        return None
    # ``response_json`` stores the URL (or empty string sentinel
    # for "no cover known"); not JSON in our case but we reuse
    # the same column so we don't need a new table.
    return row.response_json or ""


async def _cache_put(db: AsyncSession, query: str, value: str) -> None:
    existing = await db.scalar(
        select(MetadataCache).where(
            MetadataCache.provider == _CACHE_PROVIDER,
            MetadataCache.cache_key == query.lower(),
        )
    )
    now = datetime.utcnow()
    expires = now + _CACHE_TTL
    if existing is None:
        db.add(
            MetadataCache(
                provider=_CACHE_PROVIDER,
                cache_key=query.lower(),
                response_json=value,
                fetched_at=now,
                expires_at=expires,
            )
        )
    else:
        existing.response_json = value
        existing.fetched_at = now
        existing.expires_at = expires
    try:
        await db.commit()
    except Exception:
        logger.debug("scene_cover cache write failed", exc_info=True)
        await db.rollback()
