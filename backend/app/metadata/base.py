"""Base class and data types for metadata providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MetadataResult:
    provider: str
    provider_id: str
    title: str
    publisher: str | None = None
    country: str | None = None
    description: str | None = None
    cover_url: str | None = None
    issn: str | None = None
    frequency: str | None = None
    # Extended fields populated by the ISSN-first cascade. The original
    # Google Books / Internet Archive providers leave these blank;
    # ZDB / Wikidata / BnF / LoC fill them when they have the data.
    language: str | None = None  # ISO 639-1
    wikidata_qid: str | None = None  # e.g. "Q180445" for Nature
    zdb_id: str | None = None  # e.g. "120714-3"
    wikipedia_url: str | None = None
    categories: list[str] | None = None  # press, newspaper, scientific, …
    first_issued: str | None = None  # ISO date or year string
    ceased_at: str | None = None  # ISO date or year string


@dataclass
class IssueMetadata:
    number: int | None = None
    title: str | None = None
    publication_date: str | None = None  # ISO date
    cover_url: str | None = None


class MetadataProviderBase(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[MetadataResult]: ...

    @abstractmethod
    async def get_issues(self, provider_id: str) -> list[IssueMetadata]: ...
