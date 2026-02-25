"""Pydantic schemas for system endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class SystemStatus(BaseModel):
    """Response schema for GET /api/v1/system/status."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    version: str
    uptime: int
    start_time: datetime
    magazine_count: int
    issue_count: int
    issue_file_count: int
