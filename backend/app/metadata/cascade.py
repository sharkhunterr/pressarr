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
    # All ISSNs Wikidata associates with this entity — used by the
    # root-slug dedup pass to keep "Le Monde print edition" + "Le Monde
    # online" together when other providers return them as separate
    # rows. Not surfaced on the API response (internal only).
    related_issns: list[str] = field(default_factory=list)
    # Provenance list, e.g. ``["zdb", "wikidata"]`` — exposed in the
    # API so the operator can see how complete this identity is.
    sources: list[str] = field(default_factory=list)


# Per-provider soft timeout — beyond this we drop the provider's
# result and proceed with whatever the rest returned. Picked so the
# typical p95 of each upstream stays under the cap while honouring
# the user-perceived budget for an interactive search (≤6s total
# wall time once cached, ≤7s cold).
_PROVIDER_TIMEOUT = 6.0


async def _gather_with_timeout(
    coros: list, *, timeout: float = _PROVIDER_TIMEOUT
) -> list:
    """Run providers in parallel, return whatever's done within the
    timeout, drop the rest (logged as warnings). Avoids the slowest
    upstream blocking the whole cascade.
    """
    tasks = [asyncio.ensure_future(c) for c in coros]
    done, pending = await asyncio.wait(tasks, timeout=timeout)
    for p in pending:
        p.cancel()
    if pending:
        logger.warning(
            "cascade: %d provider(s) exceeded the %ss timeout and were skipped",
            len(pending),
            timeout,
        )
    return [t.result() if t in done and not t.cancelled() else [] for t in tasks]


async def search_cascade(
    query: str,
    *,
    db: AsyncSession | None = None,
    locale: str | None = None,
) -> list[MagazineIdentity]:
    """Run a free-text title search across every provider in parallel.

    Each provider is bounded by ``_PROVIDER_TIMEOUT`` — slow upstreams
    don't hold up the whole cascade. ``locale`` (ISO-2 country code)
    biases ranking toward the matching country when set.
    """
    providers = _enabled_providers(db=db, locale=locale)
    raw = await _gather_with_timeout(
        [_safe_call(p[1], "search", query) for p in providers]
    )
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

    Same per-provider timeout as the free-text search. Returns what
    the cascade has when the slowest source misses, instead of
    blocking the request waiting for it.
    """
    providers = _enabled_providers(db=db, locale=locale)
    raw = await _gather_with_timeout(
        [_safe_call(p[1], "lookup_issn", issn) for p in providers]
    )
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

    Two-pass merge: Wikidata hits seed canonical identities first,
    registering every ISSN they list under ``related_issns`` (every
    edition Wikidata knows about — print + online + historical).
    Other providers then merge into the matching canonical identity
    when any of their ISSNs hit that pre-built lookup, instead of
    spawning a separate entry per BnF edition record.

    Fallback chain when Wikidata didn't seed:
      1. Same ISSN as an existing identity → merge.
      2. Same title slug → merge.
      3. Otherwise → new identity.
    """
    by_issn: dict[str, MagazineIdentity] = {}
    by_slug: dict[str, MagazineIdentity] = {}
    out: list[MagazineIdentity] = []

    def _spawn(r: MetadataResult) -> MagazineIdentity:
        bucket = MagazineIdentity(title=r.title)
        out.append(bucket)
        by_slug[_slug(r.title)] = bucket
        return bucket

    def _index_issn(bucket: MagazineIdentity, issn: str | None) -> None:
        if issn and issn not in by_issn:
            by_issn[issn] = bucket

    # Pass 1 — seed Wikidata identities + register their related
    # ISSN list. Subsequent providers' ISSNs that appear in any
    # canonical entity's related list route into that entity.
    for source, r in rows:
        if source != "wikidata":
            continue
        bucket = _spawn(r)
        _index_issn(bucket, r.issn)
        for related in r.related_issns or []:
            _index_issn(bucket, related)
        _absorb(bucket, source, r)

    # Pass 2 — everyone else. The ISSN map now includes related
    # ISSNs from Wikidata, so a BnF row carrying the online-edition
    # ISSN of "Le Monde" lands in the same identity as the
    # Wikidata seed.
    for source, r in rows:
        if source == "wikidata":
            continue
        bucket: MagazineIdentity | None = None
        if r.issn:
            bucket = by_issn.get(r.issn)
        if bucket is None:
            bucket = by_slug.get(_slug(r.title))
        if bucket is None:
            bucket = _spawn(r)
        _index_issn(bucket, r.issn)
        _absorb(bucket, source, r)

    # Pass 3 — root-slug dedup. Strips BnF's parenthetical-suffix
    # convention ("Le Monde (Paris. 1978)" → "le-monde") + Wikidata
    # disambiguator-by-label collisions (the rare case where two
    # QIDs share the same label) into the most-enriched single
    # entity. Identities with their own ISSN that's NOT in the
    # canonical's related_issns list are left alone — they really
    # are different magazines despite the matching root slug.
    out = _dedup_root_slug(out)
    return out


def _dedup_root_slug(
    identities: list[MagazineIdentity],
) -> list[MagazineIdentity]:
    """Collapse identities with the same root slug into one canonical
    entry, picking the most-enriched as the keeper.

    Skipped when the merge candidates carry distinct Wikidata QIDs —
    Wikidata is authoritative for "these are different periodicals"
    even if they share a label (e.g. "Le Monde" the daily vs. a
    Wikidata entity for a defunct same-name magazine).
    """
    by_root: dict[str, list[int]] = {}
    for idx, i in enumerate(identities):
        root = _root_slug(i.title)
        if root:
            by_root.setdefault(root, []).append(idx)

    keep_index: set[int] = set(range(len(identities)))
    for indices in by_root.values():
        if len(indices) < 2:
            continue
        # Pick the keeper — highest "enrichment score" wins.
        def score(idx: int) -> tuple:
            i = identities[idx]
            return (
                bool(i.wikidata_qid),
                bool(i.issn),
                bool(i.cover_url),
                bool(i.wikipedia_url),
                len(i.sources),
            )
        sorted_indices = sorted(indices, key=score, reverse=True)
        keeper_idx = sorted_indices[0]
        keeper = identities[keeper_idx]
        for i in indices:
            if i == keeper_idx:
                continue
            other = identities[i]
            # Strong "these are genuinely different periodicals" signal:
            # both entries have an ISSN AND those ISSNs differ AND
            # neither's ISSN is in the keeper's Wikidata-related-ISSN
            # list. Stay separate. ("Le Monde" canonical vs.
            # "Le Monde (1860–1896)" defunct).
            related = set(keeper.related_issns or [])
            if (
                other.issn
                and keeper.issn
                and other.issn != keeper.issn
                and other.issn not in related
                and keeper.issn not in (other.related_issns or [])
            ):
                continue
            # Otherwise: the other entry shares the root title and
            # carries no contradicting ISSN — fold into the canonical.
            # Catches: same-label Wikidata sub-entities with no data,
            # case-difference duplicates, BnF parenthetical-year
            # variants pointing at the same publication.
            _merge_into(keeper, other)
            keep_index.discard(i)
    return [identities[i] for i in range(len(identities)) if i in keep_index]


def _merge_into(target: MagazineIdentity, src: MagazineIdentity) -> None:
    """Fold ``src`` into ``target`` — empty fields on the target gain
    src's value; non-empty fields stay; sources list unions."""
    for f in (
        "issn",
        "publisher",
        "country",
        "language",
        "frequency",
        "cover_url",
        "description",
        "first_issued",
        "ceased_at",
        "wikidata_qid",
        "zdb_id",
        "wikipedia_url",
    ):
        if not getattr(target, f, None) and getattr(src, f, None):
            setattr(target, f, getattr(src, f))
    target_cats = list(target.categories or [])
    src_cats = list(src.categories or [])
    if src_cats:
        target.categories = list(dict.fromkeys([*target_cats, *src_cats]))
    src_srcs = list(src.sources or [])
    if src_srcs:
        target.sources = list(dict.fromkeys([*target.sources, *src_srcs]))


_ROOT_SLUG_PAREN = re.compile(r"\s*\([^)]*\)")


def _root_slug(title: str) -> str:
    """Slug after stripping a parenthetical disambiguator (the BnF
    "(Paris. 1978)" / Wikidata "(novel)" convention). When no
    parenthetical exists this returns the same value as ``_slug``.
    """
    if not title:
        return ""
    stripped = _ROOT_SLUG_PAREN.sub("", title)
    return _slug(stripped)


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

    # Carry Wikidata's full ISSN list through so the root-slug dedup
    # pass below can use it to merge BnF/ZDB variants of the same
    # publication. Only Wikidata populates this; other providers
    # leave it empty.
    if r.related_issns:
        merged_issns = list(
            dict.fromkeys([*target.related_issns, *r.related_issns])
        )
        target.related_issns = merged_issns


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
