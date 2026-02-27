"""Abstract base class for indexer integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawSearchResult:
    """A single search result returned by an indexer."""

    guid: str
    title: str
    indexer: str
    size: int  # bytes
    age: int  # days
    protocol: str  # torrent or usenet
    seeders: int | None = None
    download_url: str | None = None
    info_url: str | None = None
    publish_date: str | None = None  # ISO datetime from Prowlarr
    categories: list[int] | None = field(default=None)


class IndexerBase(ABC):
    """Abstract base for all indexer clients."""

    @abstractmethod
    async def search(
        self, query: str, categories: list[int] | None = None
    ) -> list[RawSearchResult]: ...

    @abstractmethod
    async def rss_feed(
        self, categories: list[int] | None = None
    ) -> list[RawSearchResult]: ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]: ...
