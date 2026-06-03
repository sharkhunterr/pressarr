"""Magazine release orchestration.

Glues the enabled scene indexers (Bookys,
telecharger-magazines.org, …) to the ``magazine_release``
table. The service:

1. Asks every enabled indexer for releases matching the
   magazine's title + a couple of alias variants the
   metadata cascade populated (search_terms, normalised
   title).
2. Deduplicates within and across indexers by
   (source, source_url) — the table's unique constraint
   also enforces this at the storage layer.
3. Upserts: brand-new releases land as ``status='available'``;
   already-known rows update their hoster list + cover so a
   re-scan picks up additional mirrors the indexer added.

Called by the magazine-detail endpoint on demand (operator
clicks "Scan for releases") and — later — by a scheduled job
once we trust the scrapers' selectors enough to run them on a
cron.
"""

import json
import logging
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.indexers.magazine_scene.base import (
    MagazineSceneIndexerBase,
    MagazineSceneRelease,
)
from app.indexers.magazine_scene.bookys import BookysIndexer
from app.indexers.magazine_scene.telecharger_magazines import (
    TelechargerMagazinesIndexer,
)
from app.models.magazine import Magazine
from app.models.magazine_release import MagazineRelease
from app.services.flaresolverr import build_client as build_flaresolverr

logger = logging.getLogger(__name__)


def build_enabled_indexers(config) -> list[MagazineSceneIndexerBase]:
    """Instantiate every enabled scene indexer from the live
    config. Returns an empty list when none are enabled —
    callers handle that gracefully (no releases scraped, no
    error)."""
    indexers: list[MagazineSceneIndexerBase] = []
    if getattr(config, "bookys_enabled", False):
        # Bookys lives behind Cloudflare. Build the FlareSolverr
        # client per call so a disabled sidecar doesn't poison
        # other indexers — the Bookys instance just runs with
        # ``flaresolverr=None`` and ``search()`` short-circuits.
        flare = build_flaresolverr(config)
        if flare is None:
            logger.warning(
                "Bookys is enabled but flaresolverr_url is empty — Bookys "
                "scrapes will return no releases until a bypass endpoint "
                "is configured."
            )
        indexers.append(
            BookysIndexer(
                base_url=config.bookys_url,
                username=config.bookys_username,
                password=config.bookys_password,
                flaresolverr=flare,
            )
        )
    if getattr(config, "telecharger_magazines_enabled", False):
        indexers.append(
            TelechargerMagazinesIndexer(
                base_url=config.telecharger_magazines_url
            )
        )
    return indexers


def _queries_for_magazine(magazine: Magazine) -> list[str]:
    """Build the search-string fan-out used against each
    indexer. The cascade-side ``search_terms`` field already
    encodes operator overrides ("60 Millions consommateurs",
    "60millions"); we keep the canonical title as the first
    query so the indexer's own relevance sort doesn't get
    confused by exotic aliases."""
    queries: list[str] = []
    if magazine.title:
        queries.append(magazine.title.strip())
    raw_terms = (magazine.search_terms or "").strip()
    if raw_terms:
        # Operator entries are line- or comma-separated.
        for part in raw_terms.replace(",", "\n").splitlines():
            t = part.strip()
            if t and t not in queries:
                queries.append(t)
    return queries[:4]  # cap fan-out per indexer


async def scan_magazine_releases(
    magazine: Magazine,
    config,
    db: AsyncSession,
) -> list[MagazineRelease]:
    """Run every enabled indexer against the magazine and
    persist the results. Returns the persisted rows (existing
    rows refreshed, new rows inserted). Safe to re-run."""
    indexers = build_enabled_indexers(config)
    if not indexers:
        logger.debug(
            "No scene indexer enabled — skipping release scan for %s",
            magazine.title,
        )
        return []
    queries = _queries_for_magazine(magazine)
    if not queries:
        return []

    # Per (source, source_url) → release. The orchestrator
    # dedupes BEFORE hitting the DB so multiple queries against
    # the same indexer don't collide on the unique constraint
    # mid-loop.
    collected: dict[tuple[str, str], MagazineSceneRelease] = {}
    for indexer in indexers:
        for q in queries:
            try:
                releases = await indexer.search(q)
            except Exception:
                logger.exception(
                    "Scene indexer %s search failed for query=%r",
                    indexer.name, q,
                )
                continue
            for r in releases:
                key = (r.source, r.source_url)
                if key not in collected:
                    collected[key] = r
        try:
            await indexer.close()  # type: ignore[attr-defined]
        except Exception:
            pass

    persisted: list[MagazineRelease] = await _upsert_releases(
        magazine_id=magazine.id,
        scraped=collected.values(),
        db=db,
    )
    return persisted


async def _upsert_releases(
    *,
    magazine_id: int,
    scraped: Iterable[MagazineSceneRelease],
    db: AsyncSession,
) -> list[MagazineRelease]:
    """Apply scraped releases to the DB. Existing rows have
    their hoster list, cover and best-effort fields refreshed
    so an indexer that gains a new mirror surfaces it the next
    scan. Status / grabbed_at / status_message are preserved
    (those belong to the download dispatcher, not the
    scraper)."""
    out: list[MagazineRelease] = []
    for r in scraped:
        existing = await db.scalar(
            select(MagazineRelease).where(
                MagazineRelease.source == r.source,
                MagazineRelease.source_url == r.source_url,
            )
        )
        hoster_payload = json.dumps(
            [{"hoster": h.hoster, "url": h.url} for h in r.hoster_links]
        )
        if existing is None:
            row = MagazineRelease(
                magazine_id=magazine_id,
                source=r.source,
                source_url=r.source_url,
                title=r.title,
                issue_label=r.issue_label,
                year=r.year,
                language=r.language,
                file_format=r.file_format,
                size_bytes=r.size_bytes,
                published_at=r.published_at,
                cover_url=r.cover_url,
                hoster_links=hoster_payload,
                status="available",
            )
            db.add(row)
            out.append(row)
        else:
            existing.title = r.title
            existing.issue_label = r.issue_label or existing.issue_label
            existing.year = r.year or existing.year
            existing.language = r.language or existing.language
            existing.file_format = r.file_format or existing.file_format
            existing.size_bytes = r.size_bytes or existing.size_bytes
            existing.cover_url = r.cover_url or existing.cover_url
            existing.hoster_links = hoster_payload
            out.append(existing)
    await db.commit()
    for row in out:
        await db.refresh(row)
    return out


def serialise_release(row: MagazineRelease) -> dict:
    """Convert a MagazineRelease row into the JSON shape the
    HTTP layer hands back. Keeps the hoster list as an array
    of dicts (decoded from the Text column) so the consumer
    doesn't have to re-parse."""
    try:
        hosters = json.loads(row.hoster_links or "[]")
    except Exception:
        hosters = []
    return {
        "id": row.id,
        "magazineId": row.magazine_id,
        "source": row.source,
        "sourceUrl": row.source_url,
        "title": row.title,
        "issueLabel": row.issue_label,
        "year": row.year,
        "language": row.language,
        "fileFormat": row.file_format,
        "sizeBytes": row.size_bytes,
        "publishedAt": row.published_at,
        "coverUrl": row.cover_url,
        "hosterLinks": hosters,
        "status": row.status,
        "statusMessage": row.status_message,
        "grabbedAt": row.grabbed_at.isoformat() if row.grabbed_at else None,
        "discoveredAt": (
            row.discovered_at.isoformat() if row.discovered_at else None
        ),
    }
