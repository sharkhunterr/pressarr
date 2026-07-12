"""BnF (Bibliothèque nationale de France) provider — French press
authority.

Plugs into the ISSN-first cascade as the regional source for French
periodicals (newspapers + magazines + serials). BnF's catalogue is
exhaustive for any title published in France — covering well-known
dailies (Le Figaro, L'Équipe), consumer titles (Que Choisir, 60
Millions de Consommateurs), and tens of thousands of niche
periodicals that neither ZDB nor Wikidata index reliably.

API: SRU 1.2 over the BnF catalogue (catalogue.bnf.fr), returns
Dublin Core XML. Free, no key, no rate limit beyond standard
politeness.

Docs: https://api.bnf.fr/fr/api-catalogue-de-la-bnf-sru-au-format-xml
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.base import IssueMetadata, MetadataProviderBase, MetadataResult
from app.models.metadata_cache import MetadataCache

logger = logging.getLogger(__name__)

PROVIDER_NAME = "bnf"
SRU_URL = "https://catalogue.bnf.fr/api/SRU"
CACHE_TTL_HOURS = 24 * 7

NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}

# bib.doctype = "a" filters to periodicals (publications en série).
# Without this filter BnF returns books / theses / maps mixed in.
_DOCTYPE_SERIAL = 'bib.doctype = "a"'


class BnfProvider(MetadataProviderBase):
    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._client = httpx.AsyncClient(timeout=15.0)

    async def search(self, query: str) -> list[MetadataResult]:
        cql = f'bib.title adj "{_escape(query)}" and {_DOCTYPE_SERIAL}'
        return await self._sru(cql=cql, cache_key=f"search:{query}", max_records=20)

    async def lookup_issn(self, issn: str) -> list[MetadataResult]:
        issn_compact = issn.replace("-", "")
        cql = f'bib.issn = "{issn_compact}" and {_DOCTYPE_SERIAL}'
        return await self._sru(
            cql=cql, cache_key=f"issn:{issn_compact}", max_records=5
        )

    async def get_issues(self, provider_id: str) -> list[IssueMetadata]:
        return []

    async def fetch_frequency(self, issn: str) -> str | None:
        """Parse BnF's MARC tag 326 (Frequency) for the given ISSN.

        BnF's dublincore record doesn't carry frequency; the
        intermarcxchange schema does. Cheap follow-up query used
        by the cascade enrichment pass to fill in ``frequency``
        when Wikidata didn't surface one.

        Returns a canonical English label ("daily" / "weekly" /
        "monthly" / "quarterly" / "annual") when the French label
        maps cleanly, otherwise the raw French string so the UI
        still has something to show.
        """
        issn = _normalize_issn(issn).replace("-", "")
        cache_key = f"freq:{issn}"
        cached: str | None = None
        if self.db is not None:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                # Empty payload means "we already checked and BnF
                # had no 326 tag" — return None without re-querying.
                return cached or None

        try:
            resp = await self._client.get(
                SRU_URL,
                params={
                    "version": "1.2",
                    "operation": "searchRetrieve",
                    "query": f'bib.issn = "{issn}"',
                    "recordSchema": "intermarcxchange",
                    "maximumRecords": "1",
                },
            )
            resp.raise_for_status()
            xml = resp.text
        except Exception:
            logger.warning(
                "BnF frequency lookup failed", extra={"issn": issn}
            )
            return None

        # MARC tag 326 ``$a`` carries the French frequency string —
        # "Quotidien" / "Hebdomadaire" / "Mensuel" / etc.
        match = re.search(
            r'<mxc:datafield tag="326"[^>]*>\s*'
            r'<mxc:subfield code="a">([^<]+)</mxc:subfield>',
            xml,
        )
        raw = match.group(1).strip() if match else None
        normalised = _normalise_frequency(raw) if raw else None
        if self.db is not None:
            await self._set_cache(cache_key, normalised or "")
        return normalised

    # ------------------------------------------------------------------

    async def _sru(
        self, cql: str, cache_key: str, max_records: int = 20
    ) -> list[MetadataResult]:
        if self.db is not None:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return self._parse_xml(cached)

        params = {
            "version": "1.2",
            "operation": "searchRetrieve",
            "query": cql,
            "recordSchema": "dublincore",
            "maximumRecords": str(max_records),
        }
        try:
            resp = await self._client.get(SRU_URL, params=params)
            resp.raise_for_status()
            xml = resp.text
        except Exception:
            logger.exception("BnF SRU query failed: %s", cql)
            return []

        results = self._parse_xml(xml)
        if self.db is not None:
            await self._set_cache(cache_key, xml)
        return results

    def _parse_xml(self, xml: str) -> list[MetadataResult]:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            logger.warning("BnF returned non-XML body")
            return []

        results: list[MetadataResult] = []
        for record in root.iterfind(".//srw:record/srw:recordData/oai_dc:dc", NS):
            r = self._parse_record(record)
            if r is not None:
                results.append(r)
        return results

    @staticmethod
    def _parse_record(dc: ET.Element) -> MetadataResult | None:
        # BnF emits each property as a flat list of <dc:foo>. We pick
        # the first title (the canonical one), the most recent
        # publisher (last in the multi-value list usually = current),
        # and parse ISSN out of the identifier list.
        titles = [t.text for t in dc.iterfind("dc:title", NS) if t.text]
        if not titles:
            return None
        title = titles[0].strip()

        publishers = [p.text for p in dc.iterfind("dc:publisher", NS) if p.text]
        publisher = (publishers[-1].strip() if publishers else None)
        if publisher and "(" in publisher:
            # "SOPUSI (Paris)" → "SOPUSI". Keeps the publisher tidy
            # without losing the country (which we hard-code to FR
            # since this is the French national library).
            publisher = publisher.split("(", 1)[0].strip()

        issn: str | None = None
        ark_id: str | None = None
        for ident in dc.iterfind("dc:identifier", NS):
            text = (ident.text or "").strip()
            if text.startswith("ISSN "):
                candidate = text.split(" ", 1)[1].strip()
                if _looks_like_issn(candidate):
                    issn = _normalize_issn(candidate)
            elif text.startswith("http://catalogue.bnf.fr/ark:/"):
                ark_id = text.rsplit("/", 1)[-1]

        # Date range "1936-1948" → first_issued=1936, ceased_at=1948
        first_issued: str | None = None
        ceased_at: str | None = None
        date_el = dc.find("dc:date", NS)
        if date_el is not None and date_el.text:
            d = date_el.text.strip()
            if "-" in d:
                parts = d.split("-", 1)
                first_issued = parts[0].strip() or None
                tail = parts[1].strip()
                # "1936-" means still publishing — leave ceased_at None.
                if tail.isdigit():
                    ceased_at = tail
            else:
                first_issued = d

        # BnF emits ISO 639-2 in the dc:language element. We
        # downconvert the handful that matter; unknown codes pass
        # through unchanged to the consumer.
        lang_el = dc.find("dc:language", NS)
        language = _iso639_2_to_1(lang_el.text) if lang_el is not None and lang_el.text else None

        provider_id = ark_id or issn or title

        # The BnF dataset is French press by definition; country
        # always =FR for serials returned here.
        return MetadataResult(
            provider=PROVIDER_NAME,
            provider_id=str(provider_id),
            title=title,
            publisher=publisher,
            country="FR",
            issn=issn,
            language=language,
            first_issued=first_issued,
            ceased_at=ceased_at,
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
# Helpers (shared shape with zdb.py — duplicated here to keep each
# provider file self-contained and easy to delete if BnF disappears).
# ----------------------------------------------------------------------


def _escape(value: str) -> str:
    return value.replace('"', '\\"')


def _normalize_issn(value: str) -> str:
    cleaned = value.replace(" ", "").replace("-", "").upper()
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:]}"
    return value.strip()


def _looks_like_issn(value: str) -> bool:
    cleaned = value.replace(" ", "").replace("-", "").upper()
    return len(cleaned) == 8 and cleaned[:7].isdigit() and (
        cleaned[7].isdigit() or cleaned[7] == "X"
    )


_LANG_MAP = {
    "eng": "en", "ger": "de", "deu": "de", "fre": "fr", "fra": "fr",
    "spa": "es", "ita": "it", "por": "pt", "nld": "nl", "dut": "nl",
}


def _iso639_2_to_1(code: str) -> str | None:
    return _LANG_MAP.get(code.lower())


# BnF's MARC tag 326 emits the publication frequency as a French
# label. Mapped to the canonical English values the rest of the
# pressarr / allseerr stack already uses. Anything not in the map
# passes through verbatim so the operator still sees the original
# string (e.g. "Bimestriel", "Trimestriel : 4 n° + 1 supplément").
_FR_FREQUENCY = {
    "quotidien": "daily",
    "quotidienne": "daily",
    "hebdomadaire": "weekly",
    "bimensuel": "biweekly",
    "bimensuelle": "biweekly",
    "mensuel": "monthly",
    "mensuelle": "monthly",
    "bimestriel": "bimonthly",
    "bimestrielle": "bimonthly",
    "trimestriel": "quarterly",
    "trimestrielle": "quarterly",
    "semestriel": "semi-annual",
    "semestrielle": "semi-annual",
    "annuel": "annual",
    "annuelle": "annual",
    "irrégulier": "irregular",
    "irreg": "irregular",
}


def _normalise_frequency(raw: str) -> str:
    """Map a French BnF frequency string to the canonical English
    label when we recognise it; pass through verbatim otherwise."""
    if not raw:
        return raw
    # Strip trailing qualifiers like "Trimestriel : 4 n°…" → "Trimestriel"
    head = raw.split(":", 1)[0].strip().lower()
    return _FR_FREQUENCY.get(head, raw.strip())
