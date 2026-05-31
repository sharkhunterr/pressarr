"""ISSN-first cascade orchestrator.

Fans out a magazine search / lookup across every configured metadata
provider in parallel, then merges the results into a single
``MagazineIdentity``-shaped record per unique periodical.

Merge strategy
--------------
* Same-ISSN entries always collapse to one identity.
* Sources are weighted by category specificity for each field:
  - ISSN / publisher / first-issued / language: ZDB > BnF > LoC > Wikidata
  - cover_url / wikipedia / qid / categories: Wikidata only
  - country: Wikidata > BnF (FR) > LoC (US) > ZDB hint
* When a provider has a value and the merged record doesn't, the
  provider's value is adopted. Conflicting non-empty values keep
  the higher-priority source. Empty + empty stays empty.
* Each entry tracks its `sources` list so the operator can see which
  catalogues contributed.

The cascade itself is stateless: every call hits the providers (or
their per-provider cache, when ``db`` is provided). The caller can
persist the resulting MagazineIdentity into ``Magazine`` rows when
the operator actually adds the magazine.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.base import MetadataResult
from app.metadata.wikidata import WikidataProvider
from app.metadata.zdb import ZdbProvider

logger = logging.getLogger(__name__)


@dataclass
class MagazineIdentity:
    """The merged result of one cascade lookup — schema mirror of the
    enrichment fields we plan to persist on the ``Magazine`` row."""

    title: str
    issn: str | None = None
    publisher: str | None = None
    country: str | None = None  # ISO-2
    language: str | None = None  # ISO-2
    frequency: str | None = None
    cover_url: str | None = None
    first_issued: str | None = None  # YYYY
    ceased_at: str | None = None  # YYYY
    wikidata_qid: str | None = None
    zdb_id: str | None = None
    wikipedia_url: str | None = None
    categories: list[str] = field(default_factory=list)
    description: str | None = None
    # Provenance list, e.g. ``["zdb", "wikidata"]`` — exposed in the
    # API so the operator can see how complete this identity is.
    sources: list[str] = field(default_factory=list)


async def search_cascade(
    query: str,
    *,
    db: AsyncSession | None = None,
    locale: str | None = None,
) -> list[MagazineIdentity]:
    """Run a free-text title search across every provider in parallel.

    ``locale`` is an ISO-2 country code. When set, the regional
    catalogue for that country (BnF for FR, LoC for US — added in
    phase 3) is fanned out alongside ZDB/Wikidata and given a higher
    weight when ranking results.
    """
    providers = _enabled_providers(db=db, locale=locale)
    coros = [_safe_call(p[1], "search", query) for p in providers]
    raw = await asyncio.gather(*coros, return_exceptions=False)
    flattened = [(name, r) for (name, _), rows in zip(providers, raw) for r in rows]
    merged = _merge(flattened)
    return _rank(merged, query=query, locale=locale)


async def lookup_issn(
    issn: str,
    *,
    db: AsyncSession | None = None,
    locale: str | None = None,
) -> MagazineIdentity | None:
    """Authoritative ISSN lookup — returns the best single identity.

    Always queries every provider so we get both the ZDB canonical
    record AND the Wikidata enrichment (cover / wiki URL / qid).
    """
    providers = _enabled_providers(db=db, locale=locale)
    coros = [_safe_call(p[1], "lookup_issn", issn) for p in providers]
    raw = await asyncio.gather(*coros, return_exceptions=False)
    flattened = [(name, r) for (name, _), rows in zip(providers, raw) for r in rows]
    if not flattened:
        return None
    merged = _merge(flattened)
    return merged[0] if merged else None


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _enabled_providers(
    *, db: AsyncSession | None, locale: str | None
) -> list[tuple[str, object]]:
    """Build the parallel fan-out list. Phase-3 regional providers
    will plug in here behind a locale check.
    """
    out: list[tuple[str, object]] = [
        ("zdb", ZdbProvider(db=db)),
        ("wikidata", WikidataProvider(db=db)),
    ]
    # Regional providers added in phase 3 — keep the locale param
    # threaded through now so wiring them is a one-line append.
    _ = locale
    return out


async def _safe_call(provider: object, method: str, *args) -> list[MetadataResult]:
    try:
        result = await getattr(provider, method)(*args)
        return list(result) if result else []
    except Exception:
        logger.exception(
            "cascade: provider %s.%s failed", type(provider).__name__, method
        )
        return []


def _merge(rows: list[tuple[str, MetadataResult]]) -> list[MagazineIdentity]:
    """Collapse rows into MagazineIdentity entries.

    Key strategy:
      1. If both rows carry an ISSN and they match, merge.
      2. Else fall back to slug(title) match — handles records that
         haven't been ISSN-tagged yet (older serials, recent launches).
    """
    by_issn: dict[str, MagazineIdentity] = {}
    by_slug: dict[str, MagazineIdentity] = {}
    out: list[MagazineIdentity] = []

    for source, r in rows:
        bucket: MagazineIdentity | None = None
        if r.issn:
            bucket = by_issn.get(r.issn)
        if bucket is None:
            slug = _slug(r.title)
            bucket = by_slug.get(slug)
        if bucket is None:
            bucket = MagazineIdentity(title=r.title)
            out.append(bucket)
            by_slug[_slug(r.title)] = bucket
            if r.issn:
                by_issn[r.issn] = bucket
        else:
            # Late ISSN discovery: index the existing bucket so a
            # following ZDB row with same ISSN also lands here.
            if r.issn and r.issn not in by_issn:
                by_issn[r.issn] = bucket
        _absorb(bucket, source, r)
    return out


# Field-level priority: lower index wins when both providers have a
# value. Providers not listed always lose to listed ones.
#
# Title: Wikidata labels are concise and curated ("Nature"). ZDB titles
# carry catalogue artifacts ("Nature : international weekly journal of
# science; [Mehrjahresausgabe]"), so Wikidata wins when present.
# Publisher / language / first_issued / ISSN: ZDB is the authoritative
# library catalogue. Country: Wikidata has cleaner ISO-2 codes.
_PRIORITY = {
    "title": ["wikidata", "zdb"],
    "publisher": ["zdb", "wikidata"],
    "country": ["wikidata", "zdb"],
    "language": ["zdb", "wikidata"],
    "first_issued": ["zdb", "wikidata"],
    "ceased_at": ["wikidata", "zdb"],
    "issn": ["zdb", "wikidata"],
    "description": ["zdb", "wikidata"],
}


def _absorb(target: MagazineIdentity, source: str, r: MetadataResult) -> None:
    if source not in target.sources:
        target.sources.append(source)

    _prefer(target, "title", r.title, source)
    _prefer(target, "publisher", r.publisher, source)
    _prefer(target, "country", r.country, source)
    _prefer(target, "language", r.language, source)
    _prefer(target, "first_issued", r.first_issued, source)
    _prefer(target, "ceased_at", r.ceased_at, source)
    _prefer(target, "issn", r.issn, source)
    _prefer(target, "description", r.description, source)
    _prefer(target, "frequency", r.frequency, source)

    # Wikidata-only enrichment fields — no precedence battles.
    if r.cover_url and not target.cover_url:
        target.cover_url = r.cover_url
    if r.wikipedia_url and not target.wikipedia_url:
        target.wikipedia_url = r.wikipedia_url
    if r.wikidata_qid and not target.wikidata_qid:
        target.wikidata_qid = r.wikidata_qid
    if r.zdb_id and not target.zdb_id:
        target.zdb_id = r.zdb_id

    if r.categories:
        merged_cats = list(dict.fromkeys([*target.categories, *r.categories]))
        target.categories = merged_cats


def _prefer(
    target: MagazineIdentity, field_name: str, value: str | None, source: str
) -> None:
    if not value:
        return
    current = getattr(target, field_name, None)
    if not current:
        setattr(target, field_name, value)
        return
    priority = _PRIORITY.get(field_name, [])
    if source in priority and (
        getattr(target, "_source_for_" + field_name, None) not in priority
        or priority.index(source)
        < priority.index(getattr(target, "_source_for_" + field_name))
    ):
        setattr(target, field_name, value)
    # Track origin so a later, higher-priority provider can override.
    if not hasattr(target, "_source_for_" + field_name):
        setattr(target, "_source_for_" + field_name, source)


def _rank(
    identities: list[MagazineIdentity],
    *,
    query: str,
    locale: str | None,
) -> list[MagazineIdentity]:
    """Sort: exact-match titles first, then prefix matches, then by
    completeness (more populated fields → higher rank), then alpha.
    Locale match (when set) bubbles up titles from that country.
    """
    q = query.lower().strip()

    def key(i: MagazineIdentity) -> tuple:
        title = (i.title or "").lower().strip()
        exact = 0 if title == q else 1
        prefix = 0 if title.startswith(q) else 1
        locale_match = 0 if (locale and i.country == locale.upper()) else 1
        completeness = -sum(
            bool(getattr(i, f))
            for f in (
                "issn",
                "publisher",
                "country",
                "language",
                "cover_url",
                "wikidata_qid",
                "zdb_id",
                "first_issued",
            )
        )
        return (exact, prefix, locale_match, completeness, title)

    return sorted(identities, key=key)


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("-", (value or "").lower()).strip("-")
