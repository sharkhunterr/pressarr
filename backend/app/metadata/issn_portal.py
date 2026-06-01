"""ISSN Portal provider (portal.issn.org).

The ISSN International Centre runs the authoritative ISSN registry.
Their portal serves a free, no-auth JSON-LD record per ISSN under
``Accept: application/ld+json``. The payload is intentionally
minimal — title (key title + name aliases), country, medium
(print / online / electronic), and the **ISSN-L** ("linking ISSN")
that ties every edition of the same publication together regardless
of which individual ISSN it carries.

Why we want it
--------------

Cascade dedup so far has keyed on the ISSN string. BnF and ZDB
register one record per edition; ``Le Monde`` for example carries
ISSN 0395-2037 (print) and 1284-1250 (online) as separate
catalogue rows. Both link to the same ISSN-L = 0395-2037, and
that's the canonical "this is the same publication" signal the
cascade needs to surface a single card.

Wikidata's ``related_issns`` list partially solves this for famous
titles but doesn't cover the long tail. ISSN-L is authoritative
across every registered serial.

API
---

Free, no key, no quota beyond standard politeness:

    GET https://portal.issn.org/resource/ISSN/<issn>
    Accept: application/ld+json

The provider has no usable free-text search — the portal's HTML
search form gates JSON access — so this client only implements
``lookup_issn``. ``search`` returns empty so the base interface
still works.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.base import IssueMetadata, MetadataProviderBase, MetadataResult
from app.models.metadata_cache import MetadataCache

logger = logging.getLogger(__name__)

PROVIDER_NAME = "issn_portal"
BASE_URL = "https://portal.issn.org/resource/ISSN"
CACHE_TTL_HOURS = 24 * 30  # records change rarely; month-long TTL is fine.

# Medium codes the portal emits in the ``format`` field, normalised
# to a tidy English label. Mapped to None when we don't want to
# surface them.
_MEDIUM_LABEL = {
    "medium:Print": "Print",
    "medium:Online": "Online",
    "medium:CD-ROM": "CD-ROM",
    "medium:Microform": "Microform",
    "medium:Electronic": "Electronic",
}


class IssnPortalProvider(MetadataProviderBase):
    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._client = httpx.AsyncClient(
            timeout=8.0,
            headers={
                "Accept": "application/ld+json",
                "User-Agent": "pressarr/issn-cascade",
            },
        )

    async def search(self, query: str) -> list[MetadataResult]:
        """The portal's HTML search form gates JSON output, so we have
        no usable free-text search path. ``search`` is a no-op; the
        cascade still pulls Portal data on the ISSN-lookup leg.
        """
        return []

    async def lookup_issn(self, issn: str) -> list[MetadataResult]:
        issn = _normalize_issn(issn)
        cache_key = f"issn:{issn}"
        if self.db is not None:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return self._parse_json(cached)

        try:
            resp = await self._client.get(f"{BASE_URL}/{issn}")
            # The portal redirects to the HTML page for unknown ISSNs
            # — when JSON-LD is requested explicitly we always get a
            # 200 + ``{}`` for unknowns instead. So treat any non-2xx
            # as "not registered" and walk away quietly.
            if resp.status_code != 200:
                return []
            payload = resp.text
        except Exception:
            logger.warning(
                "ISSN Portal lookup failed", exc_info=True, extra={"issn": issn}
            )
            return []

        results = self._parse_json(payload)
        if self.db is not None and results:
            await self._set_cache(cache_key, payload)
        return results

    async def get_issues(self, provider_id: str) -> list[IssueMetadata]:
        return []

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_json(self, payload: str) -> list[MetadataResult]:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.debug("ISSN Portal returned non-JSON body")
            return []

        # The record carries the requested ISSN in ``identifier``;
        # mainTitle is the operator-facing label (often wrapped with
        # OSD control chars like u0098/u009c — strip them).
        issn = data.get("identifier")
        if not issn or not _looks_like_issn(issn):
            return []

        title = _clean_title(data.get("mainTitle") or "")
        if not title:
            # Try the alternate ``name`` field — the portal returns a
            # list of label variants when ``mainTitle`` is unset.
            names = data.get("name") or []
            if isinstance(names, list) and names:
                title = _clean_title(names[0])
        if not title:
            return []

        # ``isPartOf`` carries the ISSN-L resource URL — the trailing
        # path segment IS the ISSN-L value.
        issn_l: str | None = None
        is_part_of = data.get("isPartOf") or {}
        if isinstance(is_part_of, dict):
            url = is_part_of.get("id") or ""
            if url.startswith("http://issn.org/resource/ISSN-L/"):
                candidate = url.rsplit("/", 1)[-1].strip()
                if _looks_like_issn(candidate):
                    issn_l = _normalize_issn(candidate)

        # Country: ``spatial`` carries an ISO-3166 URL like
        # ``iso:code:3166:FR`` or a literal "iso.org/.../FR".
        country = _country_from_spatial(data.get("spatial"))

        # Format / medium — emitted as a string like "medium:Print"
        # OR as a dict {"id": "...", "label": "..."} depending on the
        # serialiser. We only use the bucket label for display.
        medium_raw = data.get("format")
        medium = _medium_label(medium_raw)

        # Description: we synthesise a short one-liner from medium +
        # country so the cascade has something to surface when
        # ZDB/Wikidata don't have one. Skipped when both are unknown.
        description: str | None = None
        if medium and country:
            description = f"{medium} edition (registered in {country})"
        elif medium:
            description = f"{medium} edition"

        return [
            MetadataResult(
                provider=PROVIDER_NAME,
                provider_id=issn,
                title=title,
                issn=issn,
                issn_l=issn_l,
                country=country,
                description=description,
            )
        ]

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

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

    async def _set_cache(self, cache_key: str, response_json: str) -> None:
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
            existing.response_json = response_json
            existing.fetched_at = now
            existing.expires_at = expires
        else:
            self.db.add(
                MetadataCache(
                    provider=PROVIDER_NAME,
                    cache_key=cache_key,
                    response_json=response_json,
                    fetched_at=now,
                    expires_at=expires,
                )
            )
        await self.db.flush()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _normalize_issn(value: str) -> str:
    cleaned = value.replace(" ", "").replace("-", "").upper()
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:]}"
    return value.strip()


def _looks_like_issn(value: str) -> bool:
    cleaned = (value or "").replace(" ", "").replace("-", "").upper()
    return len(cleaned) == 8 and cleaned[:7].isdigit() and (
        cleaned[7].isdigit() or cleaned[7] == "X"
    )


def _clean_title(raw: str) -> str:
    """Strip the OSD/ISO 5426 control chars the portal wraps the
    article around (````/````), trailing punctuation, and
    excess whitespace. ``Le Monde.`` → ``Le Monde``.
    """
    if not isinstance(raw, str):
        return ""
    cleaned = (
        raw.replace("", "")
        .replace("", "")
        .replace("", "")
        .strip()
    )
    while cleaned.endswith(("."," ",":",",")):
        cleaned = cleaned[:-1].strip()
    return cleaned


def _country_from_spatial(spatial) -> str | None:
    if not spatial:
        return None
    candidates = spatial if isinstance(spatial, list) else [spatial]
    for entry in candidates:
        text = entry if isinstance(entry, str) else (entry or {}).get("id", "")
        if not isinstance(text, str):
            continue
        # ``iso:code:3166:FR`` / ``...3166:FR``
        for sep in (":", "/"):
            tail = text.rsplit(sep, 1)[-1].strip().upper()
            if len(tail) == 2 and tail.isalpha():
                return tail
    return None


def _medium_label(value) -> str | None:
    if isinstance(value, dict):
        # ``{"id": "medium:Print", "label": "Print"}`` shape — prefer
        # the label when present.
        if isinstance(value.get("label"), str):
            return value["label"].strip() or None
        value = value.get("id")
    if isinstance(value, str):
        return _MEDIUM_LABEL.get(value, value.split(":", 1)[-1] or None)
    return None
