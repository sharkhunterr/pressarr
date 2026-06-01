"""Wikidata enrichment provider.

Wikidata's role in the cascade is enrichment of records the primary
ISSN catalogues (ZDB / BnF / LoC) already identified:

* Cover image (P18, served via Wikimedia Commons FilePath)
* Wikipedia URL for the operator-facing detail page
* Country of origin (P495 → P297 = ISO 3166-1 alpha-2)
* Language of work (P407 → P218 = ISO 639-1)
* First publication date (P571) / cease date (P576)
* Sister / preceded-by titles (P155 / P156)
* High-signal categories from the instance-of tree (magazine,
  newspaper, scientific journal, …)

It's used for ISSN lookup (deterministic match) and as a fallback
free-text lookup via Wikidata's entity-search REST API combined with
a SPARQL property fetch for the chosen QID.

Endpoint: https://query.wikidata.org/sparql (SPARQL, free, no auth).
Search:  https://www.wikidata.org/w/api.php?action=wbsearchentities (REST).

Politeness: Wikidata asks every SPARQL client to send a descriptive
User-Agent and to keep queries under the 60s server cap. Our payloads
are tiny single-entity fetches — well within the cap.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.base import IssueMetadata, MetadataProviderBase, MetadataResult
from app.models.metadata_cache import MetadataCache

logger = logging.getLogger(__name__)

PROVIDER_NAME = "wikidata"
SPARQL_URL = "https://query.wikidata.org/sparql"
SEARCH_URL = "https://www.wikidata.org/w/api.php"
CACHE_TTL_HOURS = 24 * 7

USER_AGENT = "pressarr/issn-cascade (https://github.com/kkodecs/pressarr)"

# Wikidata QIDs we treat as "this is a serial we care about". Anything
# outside this set during free-text search is skipped to keep results
# tight (no "magazine clip art" articles, etc.).
SERIAL_QIDS = {
    "Q1110794",   # magazine
    "Q11032",     # newspaper
    "Q41298",     # magazine (fr: revue)
    "Q1002697",   # periodical
    "Q5633421",   # scientific journal
    "Q15265344",  # comic magazine
    "Q12539852",  # online magazine
    "Q41607413",  # weekly newspaper
    "Q19389637",  # tabloid newspaper
}

# Map Wikidata QID → coarse pressarr category. Same vocabulary as
# the ZDB DDC mapping so the merged identity record stays consistent.
QID_CATEGORY = {
    "Q1110794": "magazine",
    "Q11032": "newspaper",
    "Q41298": "magazine",
    "Q1002697": "press",
    "Q5633421": "scientific",
    "Q15265344": "comic",
    "Q12539852": "magazine",
    "Q41607413": "newspaper",
    "Q19389637": "newspaper",
}


class WikidataProvider(MetadataProviderBase):
    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
        )

    async def search(self, query: str) -> list[MetadataResult]:
        """Free-text label search → SPARQL detail fetch per hit.

        Wikidata's SPARQL doesn't do good fuzzy text search; the
        ``wbsearchentities`` REST API handles that. We then filter
        to serial-like instances and fetch enrichment via SPARQL.
        """
        cache_key = f"search:{query}"
        if self.db is not None:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return self._parse_search_cache(cached)

        try:
            resp = await self._client.get(
                SEARCH_URL,
                params={
                    "action": "wbsearchentities",
                    "search": query,
                    "language": "en",
                    "format": "json",
                    "type": "item",
                    "limit": "20",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("Wikidata wbsearchentities failed: %s", query)
            return []

        qids = [hit["id"] for hit in (data.get("search") or []) if hit.get("id")]
        if not qids:
            return []

        # Single batched SPARQL to enrich + filter to serials in one round trip.
        results = await self._sparql_by_qids(qids)
        if self.db is not None:
            await self._set_cache(cache_key, self._serialize_for_cache(results))
        return results

    async def lookup_issn(self, issn: str) -> list[MetadataResult]:
        """Authoritative ISSN match — Wikidata stores ISSN as P236."""
        issn = _normalize_issn(issn)
        cache_key = f"issn:{issn}"
        if self.db is not None:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return self._parse_search_cache(cached)

        results = await self._sparql_by_issn(issn)
        if self.db is not None:
            await self._set_cache(cache_key, self._serialize_for_cache(results))
        return results

    async def get_issues(self, provider_id: str) -> list[IssueMetadata]:
        return []

    # ------------------------------------------------------------------
    # SPARQL queries
    # ------------------------------------------------------------------

    _BASE_SELECT = """
        SELECT ?item ?itemLabel ?issn ?publisherLabel ?countryCode
               ?languageCode ?image ?inception ?dissolved ?wikipedia ?instanceOf
        WHERE {{
          {match}
          OPTIONAL {{ ?item wdt:P236 ?issn }}
          OPTIONAL {{ ?item wdt:P123 ?publisher }}
          OPTIONAL {{ ?item wdt:P495 ?country. ?country wdt:P297 ?countryCode }}
          OPTIONAL {{ ?item wdt:P407 ?lang. ?lang wdt:P218 ?languageCode }}
          OPTIONAL {{ ?item wdt:P18 ?image }}
          OPTIONAL {{ ?item wdt:P571 ?inception }}
          OPTIONAL {{ ?item wdt:P576 ?dissolved }}
          OPTIONAL {{ ?item wdt:P31 ?instanceOf }}
          OPTIONAL {{
            ?wikipedia schema:about ?item;
                       schema:isPartOf <https://en.wikipedia.org/>.
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 200
    """

    _RELATED_PUBS_QUERY = """
        SELECT ?related ?relatedLabel ?issn ?relation WHERE {{
          {{ wd:{qid} wdt:P747 ?related. BIND("edition" AS ?relation) }}
          UNION
          {{ wd:{qid} wdt:P527 ?related. BIND("supplement" AS ?relation) }}
          UNION
          {{ ?related wdt:P361 wd:{qid}. BIND("supplement" AS ?relation) }}
          UNION
          {{ wd:{qid} wdt:P155 ?related. BIND("preceded_by" AS ?relation) }}
          UNION
          {{ wd:{qid} wdt:P156 ?related. BIND("followed_by" AS ?relation) }}
          OPTIONAL {{ ?related wdt:P236 ?issn }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,fr". }}
        }}
        LIMIT 30
    """

    async def _fetch_related_publications(self, qid: str) -> list[dict]:
        """Pull P747 (editions / translations), P527/P361 (supplement
        relationships), P155/P156 (preceded-by / followed-by) for the
        given QID in one SPARQL roundtrip. Returns a deduplicated list
        of ``{wikidata_qid, title, issn?, relation}`` dicts.
        """
        query = self._RELATED_PUBS_QUERY.format(qid=qid)
        data = await self._sparql(query)
        seen: dict[str, dict] = {}
        for b in data.get("results", {}).get("bindings", []):
            related_uri = _val(b, "related")
            if not related_uri:
                continue
            related_qid = related_uri.rsplit("/", 1)[-1]
            if related_qid == qid or related_qid in seen:
                continue
            seen[related_qid] = {
                "wikidata_qid": related_qid,
                "title": _val(b, "relatedLabel") or related_qid,
                "issn": _val(b, "issn"),
                "relation": _val(b, "relation") or "related",
            }
        return list(seen.values())

    async def _sparql_by_issn(self, issn: str) -> list[MetadataResult]:
        match = f'?item wdt:P236 "{_escape_literal(issn)}".'
        query = self._BASE_SELECT.format(match=match)
        results = self._parse_sparql(await self._sparql(query))
        await self._enrich_related(results)
        return results

    async def _sparql_by_qids(self, qids: list[str]) -> list[MetadataResult]:
        # `VALUES ?item { wd:Q123 wd:Q456 ... }` — gets all in one shot.
        values = " ".join(f"wd:{qid}" for qid in qids if _looks_like_qid(qid))
        if not values:
            return []
        match = f"VALUES ?item {{ {values} }}"
        query = self._BASE_SELECT.format(match=match)
        rows = self._parse_sparql(await self._sparql(query))
        # Filter to serial-shaped items (since wbsearchentities matches
        # anything by label, including unrelated people/places sharing
        # the magazine's name).
        rows = [r for r in rows if _is_serial(r)]
        await self._enrich_related(rows)
        return rows

    async def _enrich_related(self, rows: list[MetadataResult]) -> None:
        """Populate ``related_publications`` on hits that have a QID.

        Best-effort: a slow / failing related-publications query never
        breaks the main lookup. Sequential per-hit (parallel would
        hammer Wikidata for queries with many hits like a free-text
        search — keep it simple and skip when we have many results).
        """
        # Only enrich the top few — free-text search can return 20+
        # entities and we don't want to fire 20 SPARQL roundtrips.
        for r in rows[:5]:
            if not r.wikidata_qid:
                continue
            try:
                related = await self._fetch_related_publications(r.wikidata_qid)
                if related:
                    r.related_publications = related
            except Exception:
                logger.debug(
                    "Wikidata related-publications enrichment skipped",
                    exc_info=True,
                )

    async def _sparql(self, query: str) -> dict[str, Any]:
        # Wikidata's SPARQL endpoint sporadically returns 502/503 when
        # the WDQS cluster is overloaded. One quick retry recovers most
        # transient cases without ballooning latency on real failures.
        import asyncio
        for attempt in (1, 2):
            try:
                resp = await self._client.get(
                    SPARQL_URL,
                    params={"query": query, "format": "json"},
                    headers={"Accept": "application/sparql-results+json"},
                )
                if resp.status_code in (502, 503) and attempt == 1:
                    await asyncio.sleep(1.5)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception:
                if attempt == 1:
                    await asyncio.sleep(1.5)
                    continue
                logger.exception("Wikidata SPARQL failed")
                return {}
        return {}

    @staticmethod
    def _parse_sparql(data: dict[str, Any]) -> list[MetadataResult]:
        bindings = data.get("results", {}).get("bindings", []) if data else []
        # Wikidata returns one row per (item × multivalued property) cross
        # product. Collapse by QID so a magazine with two ISSNs + two
        # categories isn't four duplicate results.
        by_qid: dict[str, MetadataResult] = {}
        categories_per_qid: dict[str, list[str]] = {}
        issns_per_qid: dict[str, list[str]] = {}
        for b in bindings:
            item_uri = _val(b, "item")
            if not item_uri:
                continue
            qid = item_uri.rsplit("/", 1)[-1]

            entry = by_qid.get(qid)
            if entry is None:
                entry = MetadataResult(
                    provider=PROVIDER_NAME,
                    provider_id=qid,
                    title=_val(b, "itemLabel") or qid,
                    publisher=_val(b, "publisherLabel"),
                    country=_val(b, "countryCode"),
                    language=_val(b, "languageCode"),
                    cover_url=_commons_image_url(_val(b, "image")),
                    wikipedia_url=_val(b, "wikipedia"),
                    wikidata_qid=qid,
                    first_issued=_year(_val(b, "inception")),
                    ceased_at=_year(_val(b, "dissolved")),
                )
                by_qid[qid] = entry

            issn = _val(b, "issn")
            if issn:
                issns_per_qid.setdefault(qid, []).append(_normalize_issn(issn))

            inst = _val(b, "instanceOf")
            if inst:
                inst_qid = inst.rsplit("/", 1)[-1]
                cat = QID_CATEGORY.get(inst_qid)
                if cat:
                    categories_per_qid.setdefault(qid, []).append(cat)

        for qid, entry in by_qid.items():
            issns = sorted(set(issns_per_qid.get(qid, [])))
            if issns:
                entry.issn = issns[0]  # canonical: lowest-numbered ISSN
                # Surface every ISSN this QID owns so the cascade
                # can group BnF / ZDB records that share any of
                # them under the same canonical identity. "Le Monde"
                # for instance has print + online + historical
                # ISSNs that BnF returns as separate rows.
                if len(issns) > 1:
                    entry.related_issns = issns
            cats = sorted(set(categories_per_qid.get(qid, [])))
            if cats:
                entry.categories = cats

        return list(by_qid.values())

    # ------------------------------------------------------------------
    # Cache (JSON-serialised list of MetadataResult dicts).
    # ------------------------------------------------------------------

    def _serialize_for_cache(self, results: list[MetadataResult]) -> str:
        import dataclasses
        import json
        return json.dumps([dataclasses.asdict(r) for r in results])

    def _parse_search_cache(self, payload: str) -> list[MetadataResult]:
        import json
        try:
            rows = json.loads(payload)
        except json.JSONDecodeError:
            return []
        return [MetadataResult(**r) for r in rows]

    async def _get_cache(self, cache_key: str) -> str | None:
        assert self.db is not None
        now = datetime.now(UTC)
        stmt = select(MetadataCache.response_json).where(
            MetadataCache.provider == PROVIDER_NAME,
            MetadataCache.cache_key == cache_key,
            MetadataCache.expires_at > now,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _set_cache(self, cache_key: str, payload: str) -> None:
        assert self.db is not None
        now = datetime.now(UTC)
        expires = now + timedelta(hours=CACHE_TTL_HOURS)
        stmt = select(MetadataCache).where(
            MetadataCache.provider == PROVIDER_NAME,
            MetadataCache.cache_key == cache_key,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.response_json = payload
            existing.fetched_at = now
            existing.expires_at = expires
        else:
            self.db.add(
                MetadataCache(
                    provider=PROVIDER_NAME,
                    cache_key=cache_key,
                    response_json=payload,
                    fetched_at=now,
                    expires_at=expires,
                )
            )
        await self.db.flush()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _val(binding: dict[str, Any], key: str) -> str | None:
    cell = binding.get(key)
    if not cell:
        return None
    v = cell.get("value")
    return v.strip() if isinstance(v, str) and v.strip() else None


def _commons_image_url(filepath_url: str | None) -> str | None:
    """Wikidata returns ``http://commons.wikimedia.org/wiki/Special:FilePath/<file>``
    which redirects to the hosted image — we keep the URL as-is so the
    consumer can serve it through its own image proxy. Returns None
    when the field is absent.
    """
    return filepath_url


def _looks_like_qid(value: str) -> bool:
    return bool(value) and value.startswith("Q") and value[1:].isdigit()


def _year(value: str | None) -> str | None:
    """Wikidata dates come as ISO datetimes (e.g. ``1869-11-04T00:00:00Z``).
    Collapse to year for our purposes — pressarr / allseerr only ever
    surface the year for first-issued / ceased.
    """
    if not value:
        return None
    return value.split("-", 1)[0] if value[:4].isdigit() else value


def _is_serial(result: MetadataResult) -> bool:
    """Filter for free-text search to drop non-serial matches.

    We accept any QID that mapped to a category, or any item carrying
    an ISSN — both are strong signals it's a magazine / newspaper /
    journal rather than a person or unrelated topic.
    """
    if result.categories:
        return True
    if result.issn:
        return True
    return False


def _normalize_issn(issn: str) -> str:
    cleaned = issn.replace(" ", "").replace("-", "").upper()
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:]}"
    return issn.strip()


def _escape_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
