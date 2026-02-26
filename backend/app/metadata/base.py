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
