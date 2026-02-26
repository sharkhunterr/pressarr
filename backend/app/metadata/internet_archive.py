"""Internet Archive metadata provider for magazine search."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.base import IssueMetadata, MetadataProviderBase, MetadataResult
from app.models.metadata_cache import MetadataCache

logger = logging.getLogger(__name__)

PROVIDER_NAME = "internet_archive"
SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata"
CACHE_TTL_HOURS = 24


class InternetArchiveProvider(MetadataProviderBase):
    """Search Internet Archive's Magazine Rack collection."""

    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._client = httpx.AsyncClient(timeout=15.0)
        # Rate limit: 1 request/second
        self._rate_limiter = asyncio.Semaphore(1)
        self._last_request_time: float = 0.0

    async def _rate_limited_get(self, url: str, **kwargs) -> httpx.Response:
        """Make a rate-limited GET request (max 1 req/sec)."""
        async with self._rate_limiter:
            now = asyncio.get_event_loop().time()
            wait = self._last_request_time + 1.0 - now
            if wait > 0:
                await asyncio.sleep(wait)
            resp = await self._client.get(url, **kwargs)
            self._last_request_time = asyncio.get_event_loop().time()
            return resp

    async def search(self, query: str) -> list[MetadataResult]:
        cache_key = f"search:{query}"

        # Check cache
        if self.db is not None:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return self._parse_cached_search(cached)

        params = {
            "q": f"collection:magazinerack {query}",
            "output": "json",
            "rows": "20",
            "fl[]": "identifier,title,description,creator,subject",
        }

        try:
            resp = await self._rate_limited_get(SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("Internet Archive search failed for query=%s", query)
            return []

        results = self._parse_search_response(data)

        # Store in cache
        if self.db is not None:
            await self._set_cache(cache_key, json.dumps(data))

        return results

    async def get_issues(self, provider_id: str) -> list[IssueMetadata]:
        """Retrieve issue-level metadata from an Internet Archive item."""
        cache_key = f"issues:{provider_id}"

        # Check cache
        if self.db is not None:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return self._parse_cached_issues(cached)

        url = f"{METADATA_URL}/{provider_id}"
        try:
            resp = await self._rate_limited_get(url)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("Internet Archive metadata failed for id=%s", provider_id)
            return []

        issues = self._parse_item_files(data)

        # Store in cache
        if self.db is not None:
            await self._set_cache(cache_key, json.dumps(data))

        return issues

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_search_response(self, data: dict) -> list[MetadataResult]:
        results: list[MetadataResult] = []
        response = data.get("response", {})
        for doc in response.get("docs", []):
            title = doc.get("title")
            identifier = doc.get("identifier")
            if not title or not identifier:
                continue

            # description can be a string or a list
            description = doc.get("description")
            if isinstance(description, list):
                description = " ".join(description)

            results.append(
                MetadataResult(
                    provider=PROVIDER_NAME,
                    provider_id=identifier,
                    title=title,
                    description=description,
                    publisher=doc.get("creator") if isinstance(doc.get("creator"), str) else None,
                )
            )
        return results

    def _parse_cached_search(self, raw_json: str) -> list[MetadataResult]:
        try:
            data = json.loads(raw_json)
            return self._parse_search_response(data)
        except Exception:
            return []

    def _parse_item_files(self, data: dict) -> list[IssueMetadata]:
        """Parse files from item metadata to extract issues."""
        issues: list[IssueMetadata] = []
        files = data.get("files", [])

        issue_number = 0
        for file_info in files:
            name = file_info.get("name", "")
            # Only consider PDF files as issues
            if not name.lower().endswith(".pdf"):
                continue

            issue_number += 1
            title = name.rsplit(".", 1)[0]  # Strip extension

            issues.append(
                IssueMetadata(
                    number=issue_number,
                    title=title,
                    publication_date=file_info.get("mtime"),
                )
            )
        return issues

    def _parse_cached_issues(self, raw_json: str) -> list[IssueMetadata]:
        try:
            data = json.loads(raw_json)
            return self._parse_item_files(data)
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _get_cache(self, cache_key: str) -> str | None:
        assert self.db is not None
        now = datetime.now(timezone.utc)
        stmt = (
            select(MetadataCache.response_json)
            .where(
                MetadataCache.provider == PROVIDER_NAME,
                MetadataCache.cache_key == cache_key,
                MetadataCache.expires_at > now,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _set_cache(self, cache_key: str, response_json: str) -> None:
        assert self.db is not None
        now = datetime.now(timezone.utc)
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
            entry = MetadataCache(
                provider=PROVIDER_NAME,
                cache_key=cache_key,
                response_json=response_json,
                fetched_at=now,
                expires_at=expires,
            )
            self.db.add(entry)
        await self.db.flush()
