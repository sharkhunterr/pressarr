"""ZDB (Zeitschriftendatenbank — Deutsche Nationalbibliothek) provider.

ZDB is the world's largest periodicals database (~2M titles), maintained
by the German National Library. It is ISSN-indexed and covers serials
published worldwide, with strong coverage for European periodicals
(including French press, English-language scientific journals, etc.).

Why it's the right primary source for our ISSN-first cascade:

* Free. No registration, no API key, no rate limit headache.
* Authoritative. Records are curated by national libraries.
* ISSN as canonical key. Every entry carries an ISSN when one exists.
* Worldwide. Despite the German focus, ZDB indexes serials from any
  country — what isn't there typically isn't ISSN-registered either.

API: SRU (Search/Retrieve via URL) 1.1, returns Dublin Core XML.
  https://services.dnb.de/sru/zdb?version=1.1&operation=searchRetrieve
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.base import IssueMetadata, MetadataProviderBase, MetadataResult
from app.models.metadata_cache import MetadataCache

logger = logging.getLogger(__name__)

PROVIDER_NAME = "zdb"
SRU_URL = "https://services.dnb.de/sru/zdb"
CACHE_TTL_HOURS = 24 * 7  # ZDB records change rarely — week-long TTL is fine

# XML namespaces emitted by the SRU response.
NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}


class ZdbProvider(MetadataProviderBase):
    """Search ZDB for magazine / newspaper / serial metadata."""

    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._client = httpx.AsyncClient(timeout=15.0)

    async def search(self, query: str) -> list[MetadataResult]:
        """Free-text title search. CQL: ``dnb.tit=<query>``."""
        return await self._sru_query(
            cql=f"dnb.tit={_escape_cql(query)}",
            cache_key=f"search:{query}",
            max_records=20,
        )

    async def lookup_issn(self, issn: str) -> list[MetadataResult]:
        """Authoritative ISSN lookup. CQL: ``dnb.iss=NNNN-NNNN``.

        Returns a list because ZDB sometimes has multiple records
        for the same ISSN (print + electronic editions, CD-ROM, etc.).
        Caller picks the freshest or merges.
        """
        issn = _normalize_issn(issn)
        return await self._sru_query(
            cql=f"dnb.iss={issn}",
            cache_key=f"issn:{issn}",
            max_records=10,
        )

    async def get_issues(self, provider_id: str) -> list[IssueMetadata]:
        """ZDB is a title-level catalogue; no per-issue data."""
        return []

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _sru_query(
        self, cql: str, cache_key: str, max_records: int = 20
    ) -> list[MetadataResult]:
        if self.db is not None:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return self._parse_xml(cached)

        params = {
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": cql,
            "recordSchema": "oai_dc",
            "maximumRecords": str(max_records),
        }
        try:
            resp = await self._client.get(SRU_URL, params=params)
            resp.raise_for_status()
            xml = resp.text
        except Exception:
            logger.exception("ZDB SRU query failed: %s", cql)
            return []

        results = self._parse_xml(xml)
        if self.db is not None:
            await self._set_cache(cache_key, xml)
        return results

    def _parse_xml(self, xml: str) -> list[MetadataResult]:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            logger.warning("ZDB returned non-XML body")
            return []

        results: list[MetadataResult] = []
        for record in root.iterfind(".//srw:record/srw:recordData/oai_dc:dc", NS):
            r = self._parse_record(record)
            if r is not None:
                results.append(r)
        return results

    @staticmethod
    def _parse_record(dc: ET.Element) -> MetadataResult | None:
        title = _first_text(dc, "dc:title")
        if not title:
            return None
        # Cleanup ZDB's bracketed parent-title convention:
        # "[Nature <London>] ; Nature : the international journal of science"
        # → "Nature : the international journal of science"
        if ";" in title:
            title = title.split(";", 1)[1].strip()
        if title.startswith("["):
            title = title.split("]", 1)[-1].strip()

        publisher = _first_text(dc, "dc:publisher")
        if publisher and ":" in publisher:
            # "London : Macmillan" → publisher="Macmillan", country hint = London
            publisher = publisher.split(":", 1)[1].strip()

        # ZDB exposes the language as a 3-letter ISO 639-2 code; we
        # downconvert to 2-letter for our schema. Unknown codes pass
        # through as-is so we never silently drop the field.
        lang = _first_text(dc, "dc:language")
        language = _iso639_2_to_1(lang) if lang else None

        first_issued = _first_text(dc, "dc:date")

        issn: str | None = None
        zdb_id: str | None = None
        idn: str | None = None
        for ident in dc.iterfind("dc:identifier", NS):
            text = (ident.text or "").strip()
            xsi_type = ident.get("{http://www.w3.org/2001/XMLSchema-instance}type", "")
            if "ISSN" in xsi_type or text.startswith("ISSN"):
                # "ISSN der Vorlage: 0028-0836" → "0028-0836"
                if ":" in text:
                    text = text.split(":", 1)[1]
                candidate = text.strip()
                if _looks_like_issn(candidate):
                    issn = _normalize_issn(candidate)
            elif "ZDBID" in xsi_type:
                zdb_id = text
            elif "IDN" in xsi_type:
                idn = text

        provider_id = zdb_id or idn or (issn or title)

        # Optional categories from DDC subjects ("070 Nachrichtenmedien"
        # → "press"). Best-effort — DDC text is in German but the
        # leading 3-digit code is universal.
        categories: list[str] = []
        for subj in dc.iterfind("dc:subject", NS):
            cat = _ddc_to_category((subj.text or "").strip())
            if cat and cat not in categories:
                categories.append(cat)

        return MetadataResult(
            provider=PROVIDER_NAME,
            provider_id=str(provider_id),
            title=title,
            publisher=publisher,
            issn=issn,
            language=language,
            zdb_id=zdb_id,
            first_issued=first_issued,
            categories=categories or None,
        )

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

    async def _set_cache(self, cache_key: str, response_xml: str) -> None:
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
            existing.response_json = response_xml
            existing.fetched_at = now
            existing.expires_at = expires
        else:
            self.db.add(
                MetadataCache(
                    provider=PROVIDER_NAME,
                    cache_key=cache_key,
                    response_json=response_xml,
                    fetched_at=now,
                    expires_at=expires,
                )
            )
        await self.db.flush()


# ----------------------------------------------------------------------
# Module-level helpers (kept out of the class so they can be unit-tested
# without instantiating an HTTP client).
# ----------------------------------------------------------------------


def _first_text(parent: ET.Element, path: str) -> str | None:
    el = parent.find(path, NS)
    return (el.text or "").strip() if el is not None and el.text else None


def _escape_cql(value: str) -> str:
    """CQL syntax: wrap values containing special chars in quotes.

    ZDB SRU rejects bare queries with spaces — quote them to keep
    multi-word titles intact.
    """
    needs_quoting = any(c in value for c in ' "()=<>')
    if needs_quoting:
        return '"' + value.replace('"', '\\"') + '"'
    return value


def _normalize_issn(issn: str) -> str:
    """ISSN canonical form: NNNN-NNNN, hyphen, uppercase X check digit."""
    cleaned = issn.replace(" ", "").replace("-", "").upper()
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:]}"
    return issn.strip()


def _looks_like_issn(value: str) -> bool:
    cleaned = value.replace(" ", "").replace("-", "").upper()
    return len(cleaned) == 8 and cleaned[:7].isdigit() and (
        cleaned[7].isdigit() or cleaned[7] == "X"
    )


# Minimal ISO 639-2 (3-letter) → 639-1 (2-letter) map covering the
# languages ZDB actually emits in volume. Anything missing passes
# through unchanged so the consumer can still see what was returned.
_LANG_MAP = {
    "eng": "en", "ger": "de", "deu": "de", "fre": "fr", "fra": "fr",
    "spa": "es", "ita": "it", "por": "pt", "nld": "nl", "dut": "nl",
    "rus": "ru", "pol": "pl", "ces": "cs", "cze": "cs", "dan": "da",
    "swe": "sv", "nor": "no", "fin": "fi", "ell": "el", "gre": "el",
    "jpn": "ja", "zho": "zh", "chi": "zh", "kor": "ko", "ara": "ar",
    "heb": "he", "tur": "tr", "ukr": "uk", "hun": "hu",
}


def _iso639_2_to_1(code: str) -> str | None:
    return _LANG_MAP.get(code.lower())


# DDC classification → coarse category. Bindery / allseerr only need
# a handful of high-signal labels; the full DDC tree is overkill.
_DDC_CATEGORY = {
    "050": "general",
    "070": "press",  # 070 = News media, journalism, publishing
    "200": "religion",
    "300": "social",
    "330": "economics",
    "340": "law",
    "350": "politics",
    "500": "scientific",
    "510": "scientific",
    "530": "scientific",
    "540": "scientific",
    "570": "scientific",
    "610": "health",
    "640": "lifestyle",
    "700": "arts",
    "780": "music",
    "790": "entertainment",
    "796": "sports",
    "800": "literature",
    "900": "history",
}


def _ddc_to_category(subject: str) -> str | None:
    if not subject:
        return None
    prefix = subject[:3]
    return _DDC_CATEGORY.get(prefix)
