"""Magazine Pydantic schemas."""

from datetime import date, datetime

from pydantic import field_validator

from app.schemas import CamelModel


class MagazineStatistics(CamelModel):
    issue_count: int = 0
    available_count: int = 0
    missing_count: int = 0
    percent_complete: float = 0.0
    next_issue_date: date | None = None


class MagazinePatternResource(CamelModel):
    id: int
    magazine_id: int
    pattern: str
    source: str | None = None
    uploader: str | None = None
    last_seen_at: datetime
    created_at: datetime


class MagazinePatternCreateResource(CamelModel):
    pattern: str
    source: str | None = None
    uploader: str | None = None


class MagazineRuleResource(CamelModel):
    id: int
    magazine_id: int
    rule_type: str
    pattern: str


class MagazinePatternUpdateResource(CamelModel):
    pattern: str | None = None
    source: str | None = None
    uploader: str | None = None


class MagazineRuleCreateResource(CamelModel):
    rule_type: str
    pattern: str


class MagazineRuleUpdateResource(CamelModel):
    rule_type: str | None = None
    pattern: str | None = None


class MagazineResource(CamelModel):
    id: int
    title: str
    title_slug: str
    issn: str | None = None
    publisher: str | None = None
    country: str | None = None
    description: str | None = None
    frequency: str
    monitored: bool
    monitoring_start_date: date | None = None
    request_type: str = "subscription"
    target_issue_label: str | None = None
    target_issue_date: date | None = None
    search_terms: str | None = None
    cover_path: str | None = None
    use_latest_issue_cover: bool = False
    root_folder_id: int
    quality_profile_id: int
    metadata_provider_id: str | None = None
    metadata_provider: str | None = None
    added_at: datetime
    last_searched_at: datetime | None = None
    last_metadata_refresh: datetime | None = None
    excluded_days: list[int] | None = None
    patterns: list[MagazinePatternResource] = []
    rules: list[MagazineRuleResource] = []
    statistics: MagazineStatistics = MagazineStatistics()

    @field_validator("excluded_days", mode="before")
    @classmethod
    def _parse_excluded_days(cls, v: str | list[int] | None) -> list[int] | None:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return [int(d) for d in v.split(",") if d.strip() != ""]
        return v


class MagazineCreateResource(CamelModel):
    title: str
    issn: str | None = None
    publisher: str | None = None
    country: str | None = None
    description: str | None = None
    frequency: str = "monthly"
    monitored: bool = True
    monitoring_start_date: date | None = None
    # 'subscription' (default, recurring monitor) | 'one_shot'
    # (single back-issue, no further monitoring). Auto-grab
    # scheduler honours this when deciding whether to keep
    # scanning indexers for new releases.
    request_type: str = "subscription"
    target_issue_label: str | None = None
    target_issue_date: date | None = None
    search_terms: str | None = None
    root_folder_id: int
    quality_profile_id: int
    metadata_provider_id: str | None = None
    metadata_provider: str | None = None
    excluded_days: list[int] | None = None
    search_for_missing_issues: bool = True
    # ISSN-first cascade enrichment — allseerr's dispatcher forwards
    # what its search already resolved so pressarr persists the
    # complete identity without an extra cascade roundtrip. When
    # absent, ``create_magazine`` back-fills these from its own
    # cascade.lookup_issn() if an ISSN is present.
    language: str | None = None
    wikidata_qid: str | None = None
    zdb_id: str | None = None
    wikipedia_url: str | None = None
    categories: list[str] | None = None
    first_issued: str | None = None
    ceased_at: str | None = None


class MagazineUpdateResource(CamelModel):
    title: str | None = None
    frequency: str | None = None
    monitored: bool | None = None
    monitoring_start_date: date | None = None
    search_terms: str | None = None
    quality_profile_id: int | None = None
    root_folder_id: int | None = None
    excluded_days: list[int] | None = None
    use_latest_issue_cover: bool | None = None
    cover_issue_id: int | None = None


class SourceInfo(CamelModel):
    provider: str
    provider_id: str
    count: int = 1


class IssnEntry(CamelModel):
    """One ISSN under the same ISSN-L group, with its format label
    (Print / Online / DigitalCarrier / Microform). Sourced from the
    ISSN Portal ``hasPart`` collection."""

    issn: str
    format: str | None = None


class MetadataSearchResult(CamelModel):
    provider: str
    provider_id: str
    title: str
    publisher: str | None = None
    country: str | None = None
    description: str | None = None
    cover_url: str | None = None
    cover_is_logo: bool = False
    issn: str | None = None
    # Full ISSN-L sibling list when ISSN Portal returned a group
    # (print + online + CD-ROM). Surfaced as a filter signal — the
    # search-page "multi-ISSN only" toggle hides entries with
    # fewer than two siblings.
    issns: list[IssnEntry] = []
    frequency: str | None = None
    already_in_library: bool = False
    sources: list[SourceInfo] = []
    # ISSN-first cascade enrichment (populated by ZDB / Wikidata /
    # BnF / LoC). Older Google Books / Internet Archive providers
    # leave these blank — the field stays absent on the JSON wire
    # since CamelModel drops Nones.
    language: str | None = None
    wikidata_qid: str | None = None
    zdb_id: str | None = None
    wikipedia_url: str | None = None
    categories: list[str] = []
    first_issued: str | None = None
    ceased_at: str | None = None


class RelatedPublication(CamelModel):
    """One entry of the related-publications list (international
    editions / supplements / preceded-by / followed-by) surfaced
    from Wikidata's P747 / P527 / P361 / P155 / P156 properties."""

    wikidata_qid: str | None = None
    title: str
    issn: str | None = None
    relation: str | None = None  # edition / supplement / preceded_by / followed_by


class MagazineIdentitySchema(CamelModel):
    """Authoritative single-magazine identity returned by the ISSN
    lookup endpoint. Same shape as ``MetadataSearchResult`` but
    expresses "this IS the magazine" rather than "here's a candidate"
    — no ``already_in_library`` flag and ``sources`` is the list of
    provider names that contributed (not ranked candidates)."""

    title: str
    issn: str | None = None
    publisher: str | None = None
    country: str | None = None
    language: str | None = None
    frequency: str | None = None
    cover_url: str | None = None
    cover_is_logo: bool = False
    description: str | None = None
    first_issued: str | None = None
    ceased_at: str | None = None
    wikidata_qid: str | None = None
    zdb_id: str | None = None
    wikipedia_url: str | None = None
    categories: list[str] = []
    sources: list[str] = []
    related_publications: list[RelatedPublication] = []
    # Full ISSN sibling list under this publication's ISSN-L group
    # (print + online + CD-ROM + microform variants). Empty when
    # ISSN Portal didn't have the linkage.
    issns: list[IssnEntry] = []
