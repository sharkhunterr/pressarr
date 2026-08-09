"""System status, health check, and log endpoints."""

import shutil
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.version_check import check_latest_release
from app.dependencies import get_config, get_db
from app.models.issue import Issue
from app.models.magazine import Magazine
from app.schemas.system import (
    DiskSpaceResource,
    HealthCheckResource,
    SystemStatusResource,
)
from app.version import __version__

# Repo GitHub d'où on tire les releases (`owner/repo`). Overridable
# via env `PRESSARR_GITHUB_REPO` si un fork veut cibler son propre repo.
_DEFAULT_GITHUB_REPO = "jeremied/pressarr"

router = APIRouter(prefix="/api/v1/system", tags=["System"])

_start_time = time.time()


@router.get("/status", response_model=SystemStatusResource)
async def get_status(db: AsyncSession = Depends(get_db)):
    config = get_config()

    mag_count = (await db.execute(select(func.count(Magazine.id)))).scalar() or 0
    issue_count = (await db.execute(
        select(func.count(Issue.id)).where(Issue.is_forecast == False)  # noqa: E712
    )).scalar() or 0
    available_count = (
        await db.execute(
            select(func.count(Issue.id)).where(
                Issue.is_forecast == False,  # noqa: E712
                Issue.status == "available",
            )
        )
    ).scalar() or 0
    wanted_count = (
        await db.execute(
            select(func.count(Issue.id)).where(
                Issue.is_forecast == False,  # noqa: E712
                Issue.status.in_(["missing", "wanted"]),
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
        # Source unique : app/version.py — évite le drift historique où
        # `status.version` retournait "0.1.0" hard-codé alors que le
        # container tournait déjà en 0.1.47.
        version=__version__,
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


# ─── Version check (GitHub releases) ─────────────────────────────


class VersionCheckResource(BaseModel):
    current: str
    latest: str | None
    update_available: bool = Field(alias="updateAvailable")
    release_url: str | None = Field(alias="releaseUrl")
    published_at: str | None = Field(alias="publishedAt")
    error: str | None
    repo: str

    model_config = {"populate_by_name": True}


@router.get("/version-check", response_model=VersionCheckResource)
async def version_check(force: bool = Query(default=False)) -> VersionCheckResource:
    """Vérifie GitHub `releases/latest` et compare à la version courante.

    Cache 1h côté serveur (in-process). Force via `?force=true` pour
    court-circuiter le cache (bouton « Vérifier maintenant » côté UI).
    Toute erreur reseau/github est capturée dans `error` — l'appel
    n'échoue jamais côté HTTP.
    """
    import os
    repo = os.environ.get("PRESSARR_GITHUB_REPO") or _DEFAULT_GITHUB_REPO
    info = await check_latest_release(
        current_version=__version__,
        github_repo=repo,
        force=force,
    )
    return VersionCheckResource(
        current=info.current,
        latest=info.latest,
        update_available=info.update_available,
        release_url=info.release_url,
        published_at=info.published_at,
        error=info.error,
        repo=repo,
    )
