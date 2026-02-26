"""Contract tests for metadata providers with mocked HTTP responses."""

import json

import httpx
import pytest

from app.metadata.google_books import GoogleBooksProvider
from app.metadata.internet_archive import InternetArchiveProvider


# ---------------------------------------------------------------------------
# Google Books
# ---------------------------------------------------------------------------


GOOGLE_BOOKS_RESPONSE = {
    "kind": "books#volumes",
    "totalItems": 2,
    "items": [
        {
            "id": "gb-001",
            "volumeInfo": {
                "title": "National Geographic",
                "publisher": "National Geographic Society",
                "description": "A world-renowned magazine.",
                "printType": "MAGAZINE",
                "industryIdentifiers": [
                    {"type": "ISSN", "identifier": "0027-9358"}
                ],
                "imageLinks": {
                    "thumbnail": "https://books.google.com/covers/natgeo.jpg"
                },
            },
        },
        {
            "id": "gb-002",
            "volumeInfo": {
                "title": "Scientific American",
                "publisher": "Springer Nature",
                "description": "Popular science magazine.",
                "printType": "MAGAZINE",
                "industryIdentifiers": [],
                "imageLinks": {
                    "thumbnail": "https://books.google.com/covers/sciam.jpg"
                },
            },
        },
    ],
}


class TestGoogleBooksProvider:
    """Contract tests for GoogleBooksProvider."""

    @pytest.fixture
    def provider(self) -> GoogleBooksProvider:
        return GoogleBooksProvider(api_key=None, db=None)

    @pytest.mark.asyncio
    async def test_search_parses_volumes(self, provider: GoogleBooksProvider):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "printType=magazines" in str(request.url)
            return httpx.Response(200, json=GOOGLE_BOOKS_RESPONSE)

        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        results = await provider.search("national geographic")

        assert len(results) == 2
        r0 = results[0]
        assert r0.provider == "google_books"
        assert r0.provider_id == "gb-001"
        assert r0.title == "National Geographic"
        assert r0.publisher == "National Geographic Society"
        assert r0.issn == "0027-9358"
        assert r0.cover_url == "https://books.google.com/covers/natgeo.jpg"

        r1 = results[1]
        assert r1.title == "Scientific American"
        assert r1.issn is None  # no ISSN in identifiers

    @pytest.mark.asyncio
    async def test_search_with_api_key(self, provider: GoogleBooksProvider):
        provider.api_key = "my-test-key"

        def handler(request: httpx.Request) -> httpx.Response:
            assert "key=my-test-key" in str(request.url)
            return httpx.Response(200, json={"totalItems": 0, "items": []})

        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        results = await provider.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_error(self, provider: GoogleBooksProvider):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        results = await provider.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_get_issues_returns_empty(self, provider: GoogleBooksProvider):
        results = await provider.get_issues("gb-001")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_empty_items(self, provider: GoogleBooksProvider):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"totalItems": 0})

        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        results = await provider.search("nonexistent")
        assert results == []


# ---------------------------------------------------------------------------
# Internet Archive
# ---------------------------------------------------------------------------


ARCHIVE_SEARCH_RESPONSE = {
    "response": {
        "numFound": 2,
        "docs": [
            {
                "identifier": "ia-natgeo-2024",
                "title": "National Geographic",
                "description": "Iconic magazine about science and exploration.",
                "creator": "National Geographic Society",
            },
            {
                "identifier": "ia-time-2024",
                "title": "Time Magazine",
                "description": ["Weekly news magazine.", "Published since 1923."],
                "creator": "Time Inc.",
            },
        ],
    }
}


ARCHIVE_METADATA_RESPONSE = {
    "files": [
        {"name": "issue-001.pdf", "mtime": "2024-01-15"},
        {"name": "issue-002.pdf", "mtime": "2024-02-15"},
        {"name": "cover.jpg", "mtime": "2024-01-15"},  # not a PDF, should be skipped
        {"name": "issue-003.pdf", "mtime": "2024-03-15"},
    ]
}


class TestInternetArchiveProvider:
    """Contract tests for InternetArchiveProvider."""

    @pytest.fixture
    def provider(self) -> InternetArchiveProvider:
        p = InternetArchiveProvider(db=None)
        # Disable rate limiting for tests
        p._last_request_time = 0.0
        return p

    @pytest.mark.asyncio
    async def test_search_parses_docs(self, provider: InternetArchiveProvider):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "collection%3Amagazinerack" in str(request.url) or "collection:magazinerack" in str(request.url)
            return httpx.Response(200, json=ARCHIVE_SEARCH_RESPONSE)

        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        results = await provider.search("national geographic")

        assert len(results) == 2

        r0 = results[0]
        assert r0.provider == "internet_archive"
        assert r0.provider_id == "ia-natgeo-2024"
        assert r0.title == "National Geographic"
        assert r0.publisher == "National Geographic Society"
        assert r0.description == "Iconic magazine about science and exploration."

        r1 = results[1]
        assert r1.title == "Time Magazine"
        # Description should be joined from list
        assert "Weekly news magazine." in r1.description
        assert "Published since 1923." in r1.description

    @pytest.mark.asyncio
    async def test_get_issues_parses_pdf_files(self, provider: InternetArchiveProvider):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=ARCHIVE_METADATA_RESPONSE)

        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        issues = await provider.get_issues("ia-natgeo-2024")

        # Should only include PDF files (3 out of 4)
        assert len(issues) == 3
        assert issues[0].number == 1
        assert issues[0].title == "issue-001"
        assert issues[1].number == 2
        assert issues[2].number == 3

    @pytest.mark.asyncio
    async def test_search_handles_error(self, provider: InternetArchiveProvider):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        results = await provider.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_get_issues_handles_error(self, provider: InternetArchiveProvider):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        issues = await provider.get_issues("nonexistent")
        assert issues == []


# ---------------------------------------------------------------------------
# Deduplication across providers
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Test deduplication when searching across multiple providers."""

    @pytest.mark.asyncio
    async def test_deduplicate_across_providers(self):
        """Results with the same normalized title should be deduplicated."""
        from unittest.mock import AsyncMock, patch

        from app.services.magazine_service import search_metadata

        google_results = [
            type("MetadataResult", (), {
                "provider": "google_books",
                "provider_id": "gb-natgeo",
                "title": "National Geographic",
                "publisher": "NGS",
                "country": None,
                "description": None,
                "cover_url": None,
                "issn": "0027-9358",
                "frequency": None,
            })(),
        ]

        archive_results = [
            type("MetadataResult", (), {
                "provider": "internet_archive",
                "provider_id": "ia-natgeo",
                "title": "national geographic",  # same title, different case
                "publisher": None,
                "country": None,
                "description": None,
                "cover_url": None,
                "issn": None,
                "frequency": None,
            })(),
            type("MetadataResult", (), {
                "provider": "internet_archive",
                "provider_id": "ia-time",
                "title": "Time Magazine",
                "publisher": None,
                "country": None,
                "description": None,
                "cover_url": None,
                "issn": None,
                "frequency": None,
            })(),
        ]

        with (
            patch(
                "app.metadata.google_books.GoogleBooksProvider"
            ) as mock_google_cls,
            patch(
                "app.metadata.internet_archive.InternetArchiveProvider"
            ) as mock_ia_cls,
        ):
            mock_google = AsyncMock()
            mock_google.search.return_value = google_results
            mock_google_cls.return_value = mock_google

            mock_ia = AsyncMock()
            mock_ia.search.return_value = archive_results
            mock_ia_cls.return_value = mock_ia

            # config stub
            config = type("Config", (), {"google_books_api_key": None})()
            results = await search_metadata("national geographic", config)

        # "National Geographic" from google and "national geographic" from IA
        # should deduplicate to one entry; "Time Magazine" should remain.
        titles = [r.title for r in results]
        assert len(titles) == 2
        assert "National Geographic" in titles
        assert "Time Magazine" in titles
