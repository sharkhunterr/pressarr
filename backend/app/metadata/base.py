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
    # True when ``cover_url`` is a brand logo (Wikidata P154) rather
    # than a content image — the UI uses this to switch from a
    # zoom-cropped fill (which butchers logos) to a contained layout
    # with a neutral background.
    cover_is_logo: bool = False
    issn: str | None = None
    # ISSN-L (linking ISSN) — the canonical identifier shared by
    # every edition of the same publication (print + online + format
    # variants). Sourced from the ISSN Portal. The cascade uses it as
    # the primary group key so "Le Monde print" / "Le Monde online" /
    # ... never appear as separate magazine cards even when their
    # individual ISSNs differ.
    issn_l: str | None = None
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
    # Wikidata exposes every ISSN a periodical has ever carried
    # (print + online + historical editions). When the provider
    # surfaces them all the cascade can group BnF / ZDB records
    # that share any of these ISSNs under one canonical identity
    # instead of leaving "Le Monde" / "Le Monde online" / etc. as
    # apparent duplicates. Set on the canonical Wikidata hit, not
    # on per-ISSN hits.
    related_issns: list[str] | None = None
    # Alternate titles (variant labels) Wikidata stores via P1813
    # or aliases — used as fallback dedup signal when BnF doesn't
    # share an ISSN with the Wikidata canonical record.
    alt_titles: list[str] | None = None
    # Related publications surfaced from Wikidata's P747 (has edition
    # or translation), P527 / P361 (part-of relationships) — used to
    # render an "Editions / supplements" section on the detail page
    # (e.g. "Le Monde diplomatique Brasil", "Le Monde diplomatique
    # in Esperanto" for Le Monde diplomatique). Each entry is a
    # ``{wikidata_qid, title, issn?, relation}`` dict where relation
    # ∈ {"edition", "supplement", "preceded_by", "followed_by"}.
    related_publications: list[dict] | None = None


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
