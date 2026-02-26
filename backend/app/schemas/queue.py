"""Queue Pydantic schemas."""

from datetime import datetime

from app.schemas import CamelModel


class QueueItemResource(CamelModel):
    id: int
    magazine_id: int | None = None
    magazine_title: str | None = None
    issue_id: int | None = None
    issue_number: int | None = None
    title: str
    status: str  # queued, downloading, paused, postProcessing, completed, failed
    protocol: str
    download_client: str | None = None
    download_client_id: int | None = None
    download_id: str | None = None
    quality: str = "unknown"
    size: int = 0
    size_left: int = 0
    progress: float = 0.0
    speed: int = 0
    eta: int | None = None  # seconds
    added: datetime | None = None
    error_message: str | None = None


class QueueBulkDeleteRequest(CamelModel):
    ids: list[int]
    blocklist: bool = False
