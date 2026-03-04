"""System status, health check, and log endpoints."""

import shutil
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_config, get_db
from app.models.issue import Issue
from app.models.magazine import Magazine
from app.schemas.system import (
    DiskSpaceResource,
    HealthCheckResource,
    SystemStatusResource,
)

router = APIRouter(prefix="/api/v1/system", tags=["System"])

_start_time = time.time()


@router.get("/status", response_model=SystemStatusResource)
async def get_status(db: AsyncSession = Depends(get_db)):
    config = get_config()

    mag_count = (await db.execute(select(func.count(Magazine.id)))).scalar() or 0
    issue_count = (await db.execute(select(func.count(Issue.id)))).scalar() or 0
    available_count = (
        await db.execute(
            select(func.count(Issue.id)).where(Issue.status == "available")
        )
    ).scalar() or 0
    wanted_count = (
        await db.execute(
            select(func.count(Issue.id)).where(
                Issue.status.in_(["missing", "wanted"])
            )
        )
    ).scalar() or 0

    disk_space = []
    from app.models.root_folder import RootFolder

    folders = (await db.execute(select(RootFolder))).scalars().all()
    for folder in folders:
        try:
            usage = shutil.disk_usage(folder.path)
            disk_space.append(
                DiskSpaceResource(
                    path=folder.path,
                    free_space=usage.free,
                    total_space=usage.total,
                )
            )
        except OSError:
            pass

    return SystemStatusResource(
        version=config.version if hasattr(config, "version") else "0.1.0",
        start_time=datetime.fromtimestamp(_start_time, tz=UTC),
        uptime_seconds=time.time() - _start_time,
        magazine_count=mag_count,
        issue_count=issue_count,
        available_count=available_count,
        wanted_count=wanted_count,
        missing_count=wanted_count,
        queue_count=0,
        disk_space=disk_space,
    )


@router.get("/health", response_model=HealthCheckResource)
async def get_health(db: AsyncSession = Depends(get_db)):
    db_ok = True
    try:
        await db.execute(select(func.count(Magazine.id)))
    except Exception:
        db_ok = False

    return HealthCheckResource(
        database=db_ok,
        message="ok" if db_ok else "database error",
    )


@router.get("/logs")
async def get_logs(
    limit: int = Query(200, ge=1, le=2000),
    level: str | None = Query(None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR)"),
    logger_filter: str | None = Query(None, alias="logger", description="Filter by logger name substring"),
):
    """Return recent application logs from the in-memory ring buffer."""
    from app.log_buffer import log_buffer_handler

    entries = log_buffer_handler.get_entries(
        limit=limit,
        level=level,
        logger_filter=logger_filter,
    )
    return [
        {
            "timestamp": e.timestamp,
            "level": e.level,
            "logger": e.logger_name,
            "message": e.message,
        }
        for e in entries
    ]
