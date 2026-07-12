"""Google Books metadata provider for magazine search."""

import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.base import IssueMetadata, MetadataProviderBase, MetadataResult
from app.models.metadata_cache import MetadataCache

logger = logging.getLogger(__name__)

PROVIDER_NAME = "google_books"
SEARCH_URL = "https://www.googleapis.com/books/v1/volumes"
CACHE_TTL_HOURS = 24


class GoogleBooksProvider(MetadataProviderBase):
    """Search Google Books API for magazine metadata."""

    def __init__(self, api_key: str | None = None, db: AsyncSession | None = None):
        self.api_key = api_key
        self.db = db
        self._client = httpx.AsyncClient(timeout=15.0)

    async def search(self, query: str) -> list[MetadataResult]:
        cache_key = f"search:{query}"

        # Check cache
        if self.db is not None:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return self._parse_cached(cached)

        # Build request — use intitle: for better title matching.
        # printType=magazines is too restrictive (misses most non-English
        # magazines), so we search all print types and filter client-side.
        params: dict[str, str] = {
            "q": f'intitle:"{query}"',
            "maxResults": "20",
        }
        if self.api_key:
            params["key"] = self.api_key

        try:
            resp = await self._client.get(SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("Google Books search failed for query=%s", query)
            return []

        results = self._parse_volumes(data)

        # Store in cache
        if self.db is not None:
            await self._set_cache(cache_key, json.dumps(data))

        return results

    async def get_issues(self, provider_id: str) -> list[IssueMetadata]:
        """Google Books doesn't have issue-level data."""
        return []

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_volumes(self, data: dict) -> list[MetadataResult]:
        results: list[MetadataResult] = []
        for item in data.get("items", []):
            volume = item.get("volumeInfo", {})
            title = volume.get("title")
            if not title:
                continue

            # Extract ISSN from industryIdentifiers
            issn = None
            for ident in volume.get("industryIdentifiers", []):
                if ident.get("type") == "ISSN":
                    issn = ident.get("identifier")
                    break

            # Cover URL
            cover_url = None
            image_links = volume.get("imageLinks")
            if image_links:
                cover_url = image_links.get("thumbnail")

            results.append(
                MetadataResult(
                    provider=PROVIDER_NAME,
                    provider_id=item.get("id", ""),
                    title=title,
                    publisher=volume.get("publisher"),
                    description=volume.get("description"),
                    cover_url=cover_url,
                    issn=issn,
                )
            )
        return results

    def _parse_cached(self, raw_json: str) -> list[MetadataResult]:
        try:
            data = json.loads(raw_json)
            return self._parse_volumes(data)
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _get_cache(self, cache_key: str) -> str | None:
        assert self.db is not None
        now = datetime.now(UTC)
        stmt = (
            select(MetadataCache.response_json)
            .where(
                MetadataCache.provider == PROVIDER_NAME,
                MetadataCache.cache_key == cache_key,
                MetadataCache.expires_at > now,
            )
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return row

    async def _set_cache(self, cache_key: str, response_json: str) -> None:
        assert self.db is not None
        now = datetime.now(UTC)
        expires = now + timedelta(hours=CACHE_TTL_HOURS)

        # Upsert: delete old then insert
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
            entry = MetadataCache(
                provider=PROVIDER_NAME,
                cache_key=cache_key,
                response_json=response_json,
                fetched_at=now,
                expires_at=expires,
            )
            self.db.add(entry)
        await self.db.flush()
