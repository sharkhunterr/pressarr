"""Issue and issue file Pydantic schemas."""

from datetime import date, datetime

from app.schemas import CamelModel


class IssueFileResource(CamelModel):
    id: int
    path: str
    relative_path: str
    size: int
    format: str
    quality: str
    original_filename: str
    release_group: str | None = None
    language: str | None = None
    imported_at: datetime


class IssueResource(CamelModel):
    id: int
    magazine_id: int
    number: int | None = None
    volume: int | None = None
    title: str | None = None
    publication_date: date | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    status: str
    monitored: bool
    is_special: bool
    is_forecast: bool
    cover_path: str | None = None
    added_at: datetime
    file: IssueFileResource | None = None


class IssueUpdateRequest(CamelModel):
    """Partial update for an issue. Only provided fields are updated."""
    number: int | None = None
    volume: int | None = None
    title: str | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    monitored: bool | None = None
    is_special: bool | None = None
    status: str | None = None
    # File fields (applied when issue has a file)
    quality: str | None = None
    format: str | None = None
    release_group: str | None = None
    language: str | None = None
    original_filename: str | None = None


class IssueBatchMonitorRequest(CamelModel):
    issue_ids: list[int]
    monitored: bool
