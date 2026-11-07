"""Abstract base class for indexer integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def release_link(download_url: str | None, guid: str | None) -> str | None:
    """Where a release is fetched from: its download URL, else its magnet.

    Magnet-only indexers behind Prowlarr (The Pirate Bay…) return an
    empty ``downloadUrl`` and put the magnet in ``guid`` — the magnet is
    then the link a download client accepts."""
    if download_url:
        return download_url
    if guid and guid.startswith("magnet:"):
        return guid
    return None


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
    # Language code or name as advertised by the indexer's torznab
    # ``<torznab:attr name="language">``. Trusted over filename
    # parsing in the search service — a French magazine titled
    # "60 Millions de Consommateurs" otherwise gets misclassified
    # as German because the parser's regex matches the bare word
    # "de" (= "of" in French).
    language: str | None = None


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
