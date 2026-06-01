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
from app.metadata.bnf import BnfProvider
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
    """Build the parallel fan-out list. Worldwide providers always
    run; regional providers add coverage for their country when
    ``locale`` matches (or always, for the small French press
    catalogue where BnF outclasses both ZDB and Wikidata for a
    title-by-title lookup).
    """
    out: list[tuple[str, object]] = [
        ("zdb", ZdbProvider(db=db)),
        ("wikidata", WikidataProvider(db=db)),
    ]
    # BnF: French press authority. We always include it (not
    # gated on locale) because it carries titles ZDB doesn't index
    # at all (L'Équipe, Le Figaro under their canonical ISSN, …)
    # — its results merge cleanly with the rest via ISSN/title.
    out.append(("bnf", BnfProvider(db=db)))
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
# science; [Mehrjahresausgabe]"), so Wikidata wins when present, then
# BnF (also clean), then ZDB.
# Publisher / language / first_issued / ISSN: national libraries are
# authoritative (BnF for FR, ZDB worldwide). Country: BnF guarantees
# FR for its rows; Wikidata's ISO-2 codes win otherwise.
_PRIORITY = {
    "title": ["wikidata", "bnf", "zdb"],
    "publisher": ["bnf", "zdb", "wikidata"],
    "country": ["wikidata", "bnf", "zdb"],
    "language": ["bnf", "zdb", "wikidata"],
    "first_issued": ["bnf", "zdb", "wikidata"],
    "ceased_at": ["wikidata", "bnf", "zdb"],
    "issn": ["bnf", "zdb", "wikidata"],
    "description": ["zdb", "wikidata", "bnf"],
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
    """Sort: exact-match titles first, then prefix, then "is this
    actually a magazine we can request" signal tier, then completeness.

    The signal tier suppresses bare-ZDB catalogue entries that match
    the query by title but carry no ISSN, no country, and no Wikidata
    backlink — they're authority records the operator can't act on.
    Penalising them avoids burying canonical hits ("Le Monde", ISSN
    0395-2037) under a wall of "Le monde de … : collection" /
    "Le monde des grands musées" rows that share a title prefix but
    aren't requestable magazines.

    Locale match (when set) only kicks in within the same signal tier
    so an FR canonical hit always beats an FR ZDB-only entry.
    """
    q = query.lower().strip()

    def signal_tier(i: MagazineIdentity) -> int:
        # 0 = ISSN known and at least one rich provider contributed
        #     (Wikidata QID or BnF/Wikidata-derived country). This is
        #     the "real magazine" bucket.
        # 1 = ISSN known but only ZDB contributed (catalogue match
        #     without enrichment — usable but lower confidence).
        # 2 = no ISSN but at least Wikidata recognised it (popular
        #     title that lacks ISSN registration; still a real thing).
        # 3 = no ISSN, no Wikidata — pure ZDB / IA catalogue noise.
        has_issn = bool(i.issn)
        has_wd = bool(i.wikidata_qid)
        has_country = bool(i.country)
        if has_issn and (has_wd or has_country):
            return 0
        if has_issn:
            return 1
        if has_wd:
            return 2
        return 3

    def key(i: MagazineIdentity) -> tuple:
        title = (i.title or "").lower().strip()
        exact = 0 if title == q else 1
        prefix = 0 if title.startswith(q) else 1
        tier = signal_tier(i)
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
        return (exact, prefix, tier, locale_match, completeness, title)

    return sorted(identities, key=key)


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("-", (value or "").lower()).strip("-")
