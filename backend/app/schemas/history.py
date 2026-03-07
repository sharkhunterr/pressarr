"""History and blocklist schemas."""

from datetime import date, datetime

from app.schemas import CamelModel


class HistoryResource(CamelModel):
    id: int
    event_type: str
    date: datetime
    magazine_id: int | None = None
    magazine_title: str | None = None
    issue_id: int | None = None
    issue_number: int | None = None
    issue_date: date | None = None
    details: str | None = None
    data: dict | None = None


class BlocklistResource(CamelModel):
    id: int
    date: datetime
    magazine_id: int | None = None
    issue_id: int | None = None
    release_title: str
    indexer: str | None = None
    protocol: str | None = None
    reason: str | None = None


class BlocklistBulkDeleteRequest(CamelModel):
    ids: list[int]
