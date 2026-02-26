"""Command schemas for async task execution."""

from datetime import datetime
from enum import Enum

from app.schemas import CamelModel


class CommandStatus(str, Enum):
    queued = "queued"
    started = "started"
    completed = "completed"
    failed = "failed"


class CommandResource(CamelModel):
    """Response schema for a command."""

    id: int
    name: str
    status: CommandStatus
    started: datetime | None = None
    ended: datetime | None = None
    message: str | None = None
    trigger: str = "manual"


class CommandRequest(CamelModel):
    """Request schema to execute a command."""

    name: str
    body: dict | None = None
