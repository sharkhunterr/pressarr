"""Pack Pydantic schemas."""

from datetime import datetime

from app.schemas import CamelModel


class PackPatternResource(CamelModel):
    id: int
    pack_id: int
    pattern: str
    source: str | None = None
    uploader: str | None = None
    last_seen_at: datetime
    created_at: datetime


class PackPatternCreateResource(CamelModel):
    pattern: str
    source: str | None = None
    uploader: str | None = None


class PackRuleResource(CamelModel):
    id: int
    pack_id: int
    rule_type: str
    pattern: str


class PackRuleCreateResource(CamelModel):
    rule_type: str
    pattern: str


class PackStatistics(CamelModel):
    pattern_count: int = 0
    rule_count: int = 0
    total_grabs: int = 0
    last_grab_date: datetime | None = None


class PackResource(CamelModel):
    id: int
    name: str
    name_slug: str
    description: str | None = None
    search_query: str
    recurrence: str
    auto_search: bool
    auto_grab: bool
    auto_import: bool
    monitored: bool
    quality_profile_id: int
    root_folder_id: int
    added_at: datetime
    last_searched_at: datetime | None = None
    patterns: list[PackPatternResource] = []
    rules: list[PackRuleResource] = []
    statistics: PackStatistics = PackStatistics()


class PackCreateResource(CamelModel):
    name: str
    description: str | None = None
    search_query: str
    recurrence: str = "none"
    auto_search: bool = False
    auto_grab: bool = False
    auto_import: bool = False
    monitored: bool = True
    quality_profile_id: int
    root_folder_id: int


class PackUpdateResource(CamelModel):
    name: str | None = None
    description: str | None = None
    search_query: str | None = None
    recurrence: str | None = None
    auto_search: bool | None = None
    auto_grab: bool | None = None
    auto_import: bool | None = None
    monitored: bool | None = None
    quality_profile_id: int | None = None
    root_folder_id: int | None = None


class PackDispatchFileResource(CamelModel):
    filename: str
    parsed_title: str | None = None
    parsed_number: int | None = None
    parsed_year: int | None = None
    parsed_month: int | None = None
    parsed_day: int | None = None
    matched_magazine_id: int | None = None
    matched_magazine_title: str | None = None
    match_score: float = 0.0
    excluded: bool = False
    exclude_reason: str | None = None


class PackDispatchPreviewResource(CamelModel):
    pack_id: int
    download_id: str
    torrent_name: str
    files: list[PackDispatchFileResource]
    total_files: int = 0
    matched_files: int = 0
    excluded_files: int = 0
    unmatched_files: int = 0


class PackDispatchAssignment(CamelModel):
    filename: str
    magazine_id: int | None = None
    issue_id: int | None = None
    skip: bool = False


class PackDispatchRequest(CamelModel):
    download_id: str
    assignments: list[PackDispatchAssignment]
