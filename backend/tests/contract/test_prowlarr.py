"""Contract tests for the Prowlarr indexer client."""

import httpx
import pytest

from app.indexers.prowlarr import ProwlarrClient


@pytest.fixture
def prowlarr_url() -> str:
    return "http://localhost:9696"


@pytest.fixture
def prowlarr_api_key() -> str:
    return "test-api-key-123"


@pytest.fixture
def prowlarr_client(prowlarr_url: str, prowlarr_api_key: str) -> ProwlarrClient:
    return ProwlarrClient(url=prowlarr_url, api_key=prowlarr_api_key)


MOCK_SEARCH_RESULTS = [
    {
        "guid": "abc-123",
        "title": "National Geographic - January 2025",
        "indexer": {"name": "NZBgeek"},
        "size": 104857600,
        "age": 5,
        "protocol": "usenet",
        "seeders": None,
        "downloadUrl": "https://nzbgeek.info/getnzb/abc-123",
        "infoUrl": "https://nzbgeek.info/details/abc-123",
        "categories": [{"id": 7010, "name": "Books/Mags"}],
    },
    {
        "guid": "def-456",
        "title": "Time Magazine - February 2025",
        "indexer": {"name": "Torznab"},
        "size": 52428800,
        "age": 2,
        "protocol": "torrent",
        "seeders": 15,
        "downloadUrl": "https://example.com/torrent/def-456",
        "infoUrl": "https://example.com/details/def-456",
        "categories": [{"id": 7020, "name": "Books/Comics"}],
    },
]

MOCK_INDEXER_LIST = [
    {"id": 1, "name": "NZBgeek", "protocol": "usenet"},
    {"id": 2, "name": "Torznab", "protocol": "torrent"},
    {"id": 3, "name": "MyIndexer", "protocol": "torrent"},
]


@pytest.mark.asyncio
async def test_search_returns_parsed_results(
    prowlarr_client: ProwlarrClient, prowlarr_url: str
):
    """Search should parse Prowlarr response into RawSearchResult objects."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=MOCK_SEARCH_RESULTS)
    )
    prowlarr_client._client = httpx.AsyncClient(transport=transport)

    results = await prowlarr_client.search("National Geographic")

    assert len(results) == 2

    r1 = results[0]
    assert r1.guid == "abc-123"
    assert r1.title == "National Geographic - January 2025"
    assert r1.indexer == "NZBgeek"
    assert r1.size == 104857600
    assert r1.age == 5
    assert r1.protocol == "usenet"
    assert r1.seeders is None
    assert r1.download_url == "https://nzbgeek.info/getnzb/abc-123"
    assert r1.info_url == "https://nzbgeek.info/details/abc-123"
    assert r1.categories == [7010]

    r2 = results[1]
    assert r2.guid == "def-456"
    assert r2.protocol == "torrent"
    assert r2.seeders == 15


@pytest.mark.asyncio
async def test_search_sends_correct_params(
    prowlarr_client: ProwlarrClient, prowlarr_url: str, prowlarr_api_key: str
):
    """Search should send correct query params and API key header."""
    captured_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    prowlarr_client._client = httpx.AsyncClient(transport=transport)

    await prowlarr_client.search("Time Magazine", categories=[7010])

    assert captured_request is not None
    assert captured_request.headers["X-Api-Key"] == prowlarr_api_key
    assert "query=Time+Magazine" in str(captured_request.url)
    assert "type=search" in str(captured_request.url)


@pytest.mark.asyncio
async def test_search_uses_default_categories(
    prowlarr_client: ProwlarrClient,
):
    """Search with no explicit categories should use defaults [7010, 7020]."""
    captured_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    prowlarr_client._client = httpx.AsyncClient(transport=transport)

    await prowlarr_client.search("test")

    assert captured_request is not None
    url_str = str(captured_request.url)
    assert "categories=7010" in url_str
    assert "categories=7020" in url_str


@pytest.mark.asyncio
async def test_search_raises_on_http_error(
    prowlarr_client: ProwlarrClient,
):
    """Search should raise on non-2xx responses."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"error": "Unauthorized"})
    )
    prowlarr_client._client = httpx.AsyncClient(transport=transport)

    with pytest.raises(httpx.HTTPStatusError):
        await prowlarr_client.search("test")


@pytest.mark.asyncio
async def test_rss_feed_returns_results(
    prowlarr_client: ProwlarrClient,
):
    """RSS feed should parse results the same way as search."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=MOCK_SEARCH_RESULTS)
    )
    prowlarr_client._client = httpx.AsyncClient(transport=transport)

    results = await prowlarr_client.rss_feed()

    assert len(results) == 2
    assert results[0].title == "National Geographic - January 2025"


@pytest.mark.asyncio
async def test_rss_feed_sends_limit_param(
    prowlarr_client: ProwlarrClient,
):
    """RSS feed should include a limit parameter."""
    captured_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    prowlarr_client._client = httpx.AsyncClient(transport=transport)

    await prowlarr_client.rss_feed()

    assert captured_request is not None
    assert "limit=100" in str(captured_request.url)


@pytest.mark.asyncio
async def test_test_connection_success(
    prowlarr_client: ProwlarrClient,
):
    """test_connection should return True and indexer count on success."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=MOCK_INDEXER_LIST)
    )
    prowlarr_client._client = httpx.AsyncClient(transport=transport)

    is_valid, message = await prowlarr_client.test_connection()

    assert is_valid is True
    assert "3 indexers found" in message


@pytest.mark.asyncio
async def test_test_connection_failure(
    prowlarr_client: ProwlarrClient,
):
    """test_connection should return False with error message on failure."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"error": "Unauthorized"})
    )
    prowlarr_client._client = httpx.AsyncClient(transport=transport)

    is_valid, message = await prowlarr_client.test_connection()

    assert is_valid is False
    assert message  # Should have some error message


@pytest.mark.asyncio
async def test_test_connection_network_error(
    prowlarr_client: ProwlarrClient,
):
    """test_connection should handle network errors gracefully."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)
    prowlarr_client._client = httpx.AsyncClient(transport=transport)

    is_valid, message = await prowlarr_client.test_connection()

    assert is_valid is False
    assert "Connection refused" in message


@pytest.mark.asyncio
async def test_parse_result_with_string_indexer(
    prowlarr_client: ProwlarrClient,
):
    """_parse_result should handle indexer as a plain string (not dict)."""
    data = {
        "guid": "xyz-789",
        "title": "Test Magazine",
        "indexer": "SimpleIndexer",
        "size": 1024,
        "age": 1,
        "protocol": "Torrent",
        "categories": [],
    }
    result = prowlarr_client._parse_result(data)

    assert result.indexer == "SimpleIndexer"
    assert result.protocol == "torrent"  # Should be lowercased


@pytest.mark.asyncio
async def test_parse_result_with_missing_fields(
    prowlarr_client: ProwlarrClient,
):
    """_parse_result should use defaults for missing fields."""
    data = {}
    result = prowlarr_client._parse_result(data)

    assert result.guid == ""
    assert result.title == ""
    assert result.indexer == "unknown"
    assert result.size == 0
    assert result.age == 0
    assert result.protocol == "torrent"
    assert result.seeders is None
    assert result.download_url is None
    assert result.info_url is None
    assert result.categories == []


@pytest.mark.asyncio
async def test_close(prowlarr_client: ProwlarrClient):
    """close should close the underlying HTTP client without error."""
    await prowlarr_client.close()
