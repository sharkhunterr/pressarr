"""Magazine Pydantic schemas."""

from datetime import date, datetime

from pydantic import field_validator

from app.schemas import CamelModel


class MagazineStatistics(CamelModel):
    issue_count: int = 0
    available_count: int = 0
    missing_count: int = 0
    percent_complete: float = 0.0


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
    search_terms: str | None = None
    root_folder_id: int
    quality_profile_id: int
    metadata_provider_id: str | None = None
    metadata_provider: str | None = None
    excluded_days: list[int] | None = None
    search_for_missing_issues: bool = True


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


class MetadataSearchResult(CamelModel):
    provider: str
    provider_id: str
    title: str
    publisher: str | None = None
    country: str | None = None
    description: str | None = None
    cover_url: str | None = None
    issn: str | None = None
    frequency: str | None = None
    already_in_library: bool = False
    sources: list[SourceInfo] = []
