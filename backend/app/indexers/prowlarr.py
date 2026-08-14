"""Prowlarr indexer API client."""

import logging

import httpx

from app.indexers.base import IndexerBase, RawSearchResult

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [7000, 7010, 7020]


class ProwlarrClient(IndexerBase):
    """Client for the Prowlarr indexer manager API."""

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=60.0)

    async def search(
        self,
        query: str,
        categories: list[int] | None = None,
        indexer_ids: list[int] | None = None,
    ) -> list[RawSearchResult]:
        """Search via Prowlarr /api/v1/search with X-Api-Key header.

        Deux niveaux de défense contre le pattern « un indexer cassé
        empoisonne toute la requête » (observé sur Prowlarr 2.5.x où
        un indexer HS renvoyant une erreur interne fait retourner []
        à Prowlarr pour le batch complet) :

        1. **Filter par capabilities** : on drop d'abord les indexers
           qui ne supportent AUCUNE des catégories demandées (ex.
           « Grabarr Game » qui n'a pas de cat magazine).
        2. **Fan-out per-indexer** : on appelle Prowlarr N fois en
           parallèle, une par indexer. Un indexer HS renvoie [] ou
           lève, on log + continue. Les autres remontent leurs
           résultats. Résultat aggrégé en union dédupliquée par guid.
        """
        cats = categories or DEFAULT_CATEGORIES

        # Filter indexer_ids par catégorie supportée.
        if indexer_ids is not None:
            caps = await self._get_indexer_capabilities()
            if caps:
                cat_set = set(cats)
                filtered = [
                    iid for iid in indexer_ids
                    if not caps.get(iid) or (caps[iid] & cat_set)
                ]
                if filtered != indexer_ids:
                    logger.debug(
                        "Prowlarr filter: dropped incompatible indexer_ids "
                        "%s (kept %s)",
                        sorted(set(indexer_ids) - set(filtered)),
                        sorted(filtered),
                    )
                indexer_ids = filtered
            if not indexer_ids:
                return []

        # Mode « no filter » (aggregate global) : garde le comportement
        # historique en 1 appel — moins robuste mais nécessite pas de
        # connaître la liste des indexers.
        if indexer_ids is None:
            return await self._search_one(query, cats, None)

        # Fan-out parallèle : un appel par indexer_id. Isole les
        # indexers HS pour qu'ils n'empoisonnent pas le batch entier.
        import asyncio

        async def _wrap(iid: int) -> list[RawSearchResult]:
            try:
                return await self._search_one(query, cats, [iid])
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Prowlarr indexer #%s failed on query %r: %s",
                    iid, query, exc,
                )
                return []

        per_indexer = await asyncio.gather(*(_wrap(i) for i in indexer_ids))

        # Dédup par (guid, indexer) — 2 indexers peuvent proxifier la
        # même release, on garde la 1ère vue.
        seen: set[tuple[str, str]] = set()
        merged: list[RawSearchResult] = []
        for batch in per_indexer:
            for r in batch:
                key = (r.guid, r.indexer)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(r)
        return merged

    async def _search_one(
        self,
        query: str,
        categories: list[int],
        indexer_ids: list[int] | None,
    ) -> list[RawSearchResult]:
        """Single Prowlarr call — used both for aggregate mode and
        per-indexer fan-out."""
        params: dict = {"query": query, "type": "search", "categories": categories}
        if indexer_ids is not None:
            params["indexerIds"] = indexer_ids
        headers = {"X-Api-Key": self.api_key}
        resp = await self._client.get(
            f"{self.url}/api/v1/search", params=params, headers=headers
        )
        resp.raise_for_status()
        return [self._parse_result(r) for r in resp.json()]

    _CAPS_CACHE: dict[str, tuple[float, dict[int, set[int]]]] = {}
    _CAPS_TTL_S = 300.0

    async def _get_indexer_capabilities(self) -> dict[int, set[int]]:
        """Return ``{indexer_id: {category_id, ...}}`` cached ≤ 5 min.

        Cache is keyed on ``self.url`` so different Prowlarr instances
        don't overwrite each other. Empty dict on any error — callers
        skip the filter step then (fail-open, matches previous
        behaviour).
        """
        import time as _t
        cached = self._CAPS_CACHE.get(self.url)
        now = _t.monotonic()
        if cached and now - cached[0] < self._CAPS_TTL_S:
            return cached[1]
        try:
            headers = {"X-Api-Key": self.api_key}
            resp = await self._client.get(
                f"{self.url}/api/v1/indexer", headers=headers, timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Prowlarr /api/v1/indexer failed: %s", exc)
            return {}
        out: dict[int, set[int]] = {}
        for item in data:
            iid = item.get("id")
            if iid is None:
                continue
            cats: set[int] = set()
            for cat in item.get("capabilities", {}).get("categories", []):
                cid = cat.get("id")
                if cid is not None:
                    cats.add(int(cid))
                for sub in cat.get("subCategories", []):
                    sid = sub.get("id")
                    if sid is not None:
                        cats.add(int(sid))
            out[int(iid)] = cats
        self._CAPS_CACHE[self.url] = (now, out)
        return out

    async def rss_feed(
        self,
        categories: list[int] | None = None,
        indexer_ids: list[int] | None = None,
    ) -> list[RawSearchResult]:
        """Get RSS feed from Prowlarr."""
        cats = categories or DEFAULT_CATEGORIES
        params: dict = {"categories": cats, "type": "search", "limit": 100}
        if indexer_ids is not None:
            params["indexerIds"] = indexer_ids
        headers = {"X-Api-Key": self.api_key}
        resp = await self._client.get(
            f"{self.url}/api/v1/search", params=params, headers=headers
        )
        resp.raise_for_status()
        return [self._parse_result(r) for r in resp.json()]

    async def test_connection(self) -> tuple[bool, str, list[dict]]:
        """Test connection by fetching the indexer list.

        Returns (is_valid, message, indexers) where indexers is a list of
        dicts with id, name and categories for each Prowlarr indexer.
        """
        try:
            headers = {"X-Api-Key": self.api_key}
            resp = await self._client.get(
                f"{self.url}/api/v1/indexer", headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
            indexers: list[dict] = []
            for item in data:
                caps = item.get("capabilities", {})
                cat_list = caps.get("categories", [])
                cat_ids: list[int] = []
                for cat in cat_list:
                    cat_id = cat.get("id")
                    if cat_id is not None:
                        cat_ids.append(cat_id)
                    for sub in cat.get("subCategories", []):
                        sub_id = sub.get("id")
                        if sub_id is not None:
                            cat_ids.append(sub_id)
                indexers.append({
                    "id": item.get("id", 0),
                    "name": item.get("name", "unknown"),
                    "categories": sorted(set(cat_ids)),
                })
            return True, f"Connected. {len(data)} indexers found.", indexers
        except Exception as e:
            return False, str(e), []

    def _parse_result(self, data: dict) -> RawSearchResult:
        """Parse a Prowlarr search result into a RawSearchResult."""
        indexer_data = data.get("indexer")
        if isinstance(indexer_data, dict):
            indexer_name = indexer_data.get("name", "unknown")
        else:
            indexer_name = data.get("indexer", "unknown")

        # Prowlarr surfaces the torznab ``<attr name="language">`` via
        # a top-level ``language`` field (when the indexer ships one).
        # Some indexers return a ``languages`` list, others a single
        # string like "French" / "fr" / "en-US". Normalise here so
        # the search service gets a single lowercase code/name; the
        # parser's ``_LANGUAGE_MAP`` does the rest.
        raw_lang = data.get("language") or (data.get("languages") or [None])[0]
        language: str | None = None
        if isinstance(raw_lang, dict):
            raw_lang = raw_lang.get("name") or raw_lang.get("value")
        if isinstance(raw_lang, str) and raw_lang.strip():
            language = raw_lang.strip().lower().split("-", 1)[0]

        return RawSearchResult(
            guid=data.get("guid", ""),
            title=data.get("title", ""),
            indexer=indexer_name,
            size=data.get("size", 0),
            age=data.get("age", 0),
            protocol=data.get("protocol", "torrent").lower(),
            seeders=data.get("seeders"),
            download_url=data.get("downloadUrl"),
            info_url=data.get("infoUrl"),
            publish_date=data.get("publishDate"),
            categories=[
                c.get("id")
                for c in data.get("categories", [])
                if isinstance(c, dict)
            ],
            language=language,
        )

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
