"""System status and health check schemas."""

from datetime import datetime

from app.schemas import CamelModel


class DiskSpaceResource(CamelModel):
    path: str
    free_space: int
    total_space: int


class SystemStatusResource(CamelModel):
    version: str
    start_time: datetime
    uptime_seconds: float
    magazine_count: int
    issue_count: int
    available_count: int
    wanted_count: int
    missing_count: int
    queue_count: int
    disk_space: list[DiskSpaceResource] = []


class HealthCheckResource(CamelModel):
    database: bool
    indexer: bool | None = None
    download_client: bool | None = None
    message: str = "ok"


class LogEntryResource(CamelModel):
    timestamp: datetime
    level: str
    logger: str
    message: str
