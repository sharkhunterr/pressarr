"""Indexer and download client Pydantic schemas."""

from app.schemas import CamelModel


class IndexerConfigResource(CamelModel):
    """Response schema for an indexer config (api_key excluded per NFR-009)."""

    id: int
    name: str
    url: str
    # NOTE: api_key is NEVER exposed in GET responses (NFR-009)
    categories: str
    enabled: bool


class IndexerConfigCreateResource(CamelModel):
    """Request schema to create an indexer config."""

    name: str
    url: str
    api_key: str
    categories: str = "7010,7020"
    enabled: bool = True


class IndexerConfigUpdateResource(CamelModel):
    """Request schema to update an indexer config."""

    name: str | None = None
    url: str | None = None
    api_key: str | None = None
    categories: str | None = None
    enabled: bool | None = None


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
    is_default: bool | None = None
    priority: int | None = None


class TestResult(CamelModel):
    """Response schema for a connection test result."""

    is_valid: bool
    message: str
