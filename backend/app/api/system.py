"""System status endpoint — public, no authentication required."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.schemas.system import SystemStatus

router = APIRouter()


@router.get("/status", response_model=SystemStatus)
async def get_system_status(request: Request) -> SystemStatus:
    """Return system health and info. Compatible with Homepage/Homarr widgets."""
    start_time: datetime = request.app.state.start_time
    now = datetime.now(timezone.utc)
    uptime = int((now - start_time).total_seconds())

    return SystemStatus(
        version="0.1.0",
        uptime=uptime,
        start_time=start_time,
        magazine_count=0,
        issue_count=0,
        issue_file_count=0,
    )
