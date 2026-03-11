"""Indexer and download client Pydantic schemas."""

from app.schemas import CamelModel


class IndexerOverrideEntry(CamelModel):
    """Per-Prowlarr-indexer override settings."""

    enabled: bool = True
    categories: str | None = None


class IndexerConfigResource(CamelModel):
    """Response schema for an indexer config (api_key excluded per NFR-009)."""

    id: int
    name: str
    url: str
    # NOTE: api_key is NEVER exposed in GET responses (NFR-009)
    categories: str
    enabled: bool
    indexer_overrides: dict[str, IndexerOverrideEntry] = {}


class IndexerConfigCreateResource(CamelModel):
    """Request schema to create an indexer config."""

    name: str
    url: str
    api_key: str
    categories: str = "7000,7010,7020"
    enabled: bool = True
    indexer_overrides: dict[str, IndexerOverrideEntry] = {}


class IndexerConfigUpdateResource(CamelModel):
    """Request schema to update an indexer config."""

    name: str | None = None
    url: str | None = None
    api_key: str | None = None
    categories: str | None = None
    enabled: bool | None = None
    indexer_overrides: dict[str, IndexerOverrideEntry] | None = None


class DownloadClientResource(CamelModel):
    """Response schema for a download client (password/api_key excluded per NFR-009)."""

    id: int
    name: str
    client_type: str
    protocol: str
    host: str
    port: int
    use_ssl: bool
    username: str | None = None
    # NOTE: password and api_key NEVER exposed in GET responses
    category: str
    remote_path: str | None = None
    local_path: str | None = None
    is_default: bool
    priority: int


class DownloadClientCreateResource(CamelModel):
    """Request schema to create a download client."""

    name: str
    client_type: str  # deluge, qbittorrent, transmission, sabnzbd, nzbget
    protocol: str  # torrent, usenet
    host: str
    port: int
    use_ssl: bool = False
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    category: str = "pressarr"
    remote_path: str | None = None
    local_path: str | None = None
    is_default: bool = False
    priority: int = 1


class DownloadClientUpdateResource(CamelModel):
    """Request schema to update a download client."""

    name: str | None = None
    host: str | None = None
    port: int | None = None
    use_ssl: bool | None = None
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    category: str | None = None
    remote_path: str | None = None
    local_path: str | None = None
    is_default: bool | None = None
    priority: int | None = None


class IndexerTestResource(CamelModel):
    """Request schema to test an indexer connection (only url + api_key needed)."""

    url: str
    api_key: str


class DownloadClientTestResource(CamelModel):
    """Request schema to test a download client connection (no name/protocol required)."""

    client_type: str
    host: str
    port: int
    use_ssl: bool = False
    username: str | None = None
    password: str | None = None
    api_key: str | None = None


class ProwlarrIndexerInfo(CamelModel):
    """Info about a single Prowlarr indexer returned after a test."""

    id: int
    name: str
    categories: list[int] = []


class TestResult(CamelModel):
    """Response schema for a connection test result."""

    is_valid: bool
    message: str
    indexers: list[ProwlarrIndexerInfo] = []
