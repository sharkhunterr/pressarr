"""Prowlarr indexer API client."""

import httpx

from app.indexers.base import IndexerBase, RawSearchResult


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
        """Search via Prowlarr /api/v1/search with X-Api-Key header."""
        cats = categories or DEFAULT_CATEGORIES
        params: dict = {"query": query, "type": "search", "categories": cats}
        if indexer_ids is not None:
            params["indexerIds"] = indexer_ids
        headers = {"X-Api-Key": self.api_key}
        resp = await self._client.get(
            f"{self.url}/api/v1/search", params=params, headers=headers
        )
        resp.raise_for_status()
        return [self._parse_result(r) for r in resp.json()]

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
