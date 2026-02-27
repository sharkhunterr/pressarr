"""Magazine management API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_config, get_db
from app.schemas.magazine import (
    MagazineCreateResource,
    MagazineResource,
    MagazineStatistics,
    MagazineUpdateResource,
    MetadataSearchResult,
)
from app.services import magazine_service
from app.services.command_service import execute_command, register_command

router = APIRouter(prefix="/api/v1/magazine", tags=["Magazines"])


async def _handle_refresh_magazine(magazine_id: int) -> str | None:
    """Command handler for RefreshMagazine."""
    from app.database import async_session_factory
    from app.services.calendar_service import generate_forecasts

    if async_session_factory is None:
        return "Database not initialized"

    async with async_session_factory() as session:
        result = await magazine_service.refresh_metadata(session, magazine_id)
        # Regenerate forecasts so they reflect current data
        magazine = await magazine_service.get_magazine(session, magazine_id)
        if magazine:
            await generate_forecasts(session, magazine)
        await session.commit()
        return result


register_command("RefreshMagazine", _handle_refresh_magazine)


@router.get("/lookup", response_model=list[MetadataSearchResult])
async def lookup_metadata(
    query: str = Query(..., min_length=1),
    config=Depends(get_config),
    db: AsyncSession = Depends(get_db),
):
    """Search metadata providers for magazine information."""
    results = await magazine_service.search_metadata(query, config, db=db)
    return results


@router.get("", response_model=list[MagazineResource])
async def list_magazines(
    sort_key: str = Query("title", alias="sortKey"),
    sort_dir: str = Query("asc", alias="sortDir"),
    monitored: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all magazines with optional filtering and sorting."""
    magazines = await magazine_service.list_magazines(
        db, sort_key=sort_key, sort_dir=sort_dir, monitored=monitored
    )
    result = []
    for mag in magazines:
        stats = await magazine_service.get_statistics(db, mag.id)
        resource = MagazineResource.model_validate(mag)
        resource.statistics = MagazineStatistics(**stats)
        result.append(resource)
    return result


@router.get("/{magazine_id}", response_model=MagazineResource)
async def get_magazine(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single magazine with computed statistics."""
    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")

    stats = await magazine_service.get_statistics(db, magazine_id)
    resource = MagazineResource.model_validate(magazine)
    resource.statistics = MagazineStatistics(**stats)
    return resource


@router.post("", response_model=MagazineResource, status_code=201)
async def create_magazine(
    body: MagazineCreateResource,
    db: AsyncSession = Depends(get_db),
):
    """Create a new magazine. Returns 409 if title slug already exists."""
    try:
        magazine = await magazine_service.create_magazine(
            db, body.model_dump(exclude={"search_for_missing_issues"})
        )
    except ValueError as e:
        raise HTTPException(409, str(e))

    stats = await magazine_service.get_statistics(db, magazine.id)
    resource = MagazineResource.model_validate(magazine)
    resource.statistics = MagazineStatistics(**stats)
    return resource


@router.put("/{magazine_id}", response_model=MagazineResource)
async def update_magazine(
    magazine_id: int,
    body: MagazineUpdateResource,
    db: AsyncSession = Depends(get_db),
):
    """Update a magazine."""
    magazine = await magazine_service.update_magazine(
        db, magazine_id, body.model_dump(exclude_none=True)
    )
    if magazine is None:
        raise HTTPException(404, "Magazine not found")

    stats = await magazine_service.get_statistics(db, magazine_id)
    resource = MagazineResource.model_validate(magazine)
    resource.statistics = MagazineStatistics(**stats)
    return resource


@router.delete("/{magazine_id}", status_code=204)
async def delete_magazine(
    magazine_id: int,
    delete_files: bool = Query(False, alias="deleteFiles"),
    db: AsyncSession = Depends(get_db),
):
    """Delete a magazine and optionally its files."""
    deleted = await magazine_service.delete_magazine(db, magazine_id, delete_files)
    if not deleted:
        raise HTTPException(404, "Magazine not found")


@router.get("/{magazine_id}/cover")
async def get_cover(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Serve the cover image for a magazine."""
    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")

    if not magazine.cover_path:
        raise HTTPException(404, "No cover available")

    cover_path = Path(magazine.cover_path)
    if not cover_path.is_file():
        raise HTTPException(404, "Cover file not found on disk")

    return FileResponse(cover_path)


@router.post("/{magazine_id}/refresh", status_code=200)
async def refresh_magazine(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a RefreshMagazine command."""
    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")

    command = await execute_command(
        "RefreshMagazine",
        body={"magazine_id": magazine_id},
    )
    return command
