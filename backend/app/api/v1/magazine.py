"""Magazine management API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_config, get_db
from app.schemas.magazine import (
    MagazineCreateResource,
    MagazinePatternCreateResource,
    MagazinePatternResource,
    MagazineResource,
    MagazineRuleCreateResource,
    MagazineRuleResource,
    MagazineStatistics,
    MagazineUpdateResource,
    MetadataSearchResult,
)
from app.services.smart_matcher import invalidate_pattern_cache
from app.services import magazine_service
from app.services.command_service import execute_command, register_command

router = APIRouter(prefix="/api/v1/magazine", tags=["Magazines"])


async def _handle_refresh_magazine(magazine_id: int) -> str | None:
    """Command handler for RefreshMagazine.

    Full refresh: metadata + disk scan + auto-detect + mark missing.
    """
    from app.database import async_session_factory
    from app.services.calendar_service import generate_forecasts

    if async_session_factory is None:
        return "Database not initialized"

    async with async_session_factory() as session:
        stats = await magazine_service.refresh_magazine_full(session, magazine_id)
        # Regenerate forecasts so they reflect current data
        magazine = await magazine_service.get_magazine(session, magazine_id)
        if magazine:
            await generate_forecasts(session, magazine)
        await session.commit()

        parts = []
        if stats.get("metadata"):
            parts.append(stats["metadata"])
        if stats.get("scanned"):
            parts.append(f"{stats['scanned']} files found")
        if stats.get("detected"):
            parts.append(f"{stats['detected']} issues auto-detected")
        if stats.get("reassigned"):
            parts.append(f"{stats['reassigned']} files reassigned")
        if stats.get("missing_cleared"):
            parts.append(f"{stats['missing_cleared']} missing files cleared")
        return "; ".join(parts) if parts else "Refresh complete"


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


@router.post("/{magazine_id}/cover", response_model=MagazineResource)
async def upload_cover(
    magazine_id: int,
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Upload a custom cover image from a file or URL."""
    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    covers_dir = Path(config.config_path).parent / "covers"

    if file and file.filename:
        if file.content_type not in allowed_types:
            raise HTTPException(400, f"Invalid image type: {file.content_type}")
        image_bytes = await file.read()
    elif url:
        import httpx

        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            raise HTTPException(400, "Failed to download image from URL")
        content_type = resp.headers.get("content-type", "").split(";")[0].strip()
        if content_type not in allowed_types:
            raise HTTPException(400, f"Invalid image type: {content_type}")
        image_bytes = resp.content
    else:
        raise HTTPException(400, "Provide either a file or a URL")

    saved_path = magazine_service.save_cover_image(
        image_bytes, covers_dir, magazine.title_slug,
    )
    magazine.cover_path = saved_path
    await db.flush()
    await db.commit()

    stats = await magazine_service.get_statistics(db, magazine_id)
    resource = MagazineResource.model_validate(magazine)
    resource.statistics = MagazineStatistics(**stats)
    return resource


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


# ---------------------------------------------------------------------------
# Pattern management
# ---------------------------------------------------------------------------


@router.post(
    "/{magazine_id}/pattern",
    response_model=MagazinePatternResource,
    status_code=201,
)
async def add_pattern(
    magazine_id: int,
    body: MagazinePatternCreateResource,
    db: AsyncSession = Depends(get_db),
):
    """Add a naming pattern for a magazine."""
    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")
    pattern = await magazine_service.add_magazine_pattern(
        db, magazine_id, body.model_dump()
    )
    await db.commit()
    invalidate_pattern_cache(magazine_id)
    return MagazinePatternResource.model_validate(pattern)


@router.delete("/{magazine_id}/pattern/{pattern_id}", status_code=204)
async def delete_pattern(
    magazine_id: int,
    pattern_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a naming pattern."""
    if not await magazine_service.delete_magazine_pattern(db, pattern_id):
        raise HTTPException(404, "Pattern not found")
    await db.commit()
    invalidate_pattern_cache(magazine_id)


# ---------------------------------------------------------------------------
# Rule management
# ---------------------------------------------------------------------------


@router.post(
    "/{magazine_id}/rule",
    response_model=MagazineRuleResource,
    status_code=201,
)
async def add_rule(
    magazine_id: int,
    body: MagazineRuleCreateResource,
    db: AsyncSession = Depends(get_db),
):
    """Add an include/exclude rule for a magazine."""
    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")
    rule = await magazine_service.add_magazine_rule(
        db, magazine_id, body.model_dump()
    )
    await db.commit()
    return MagazineRuleResource.model_validate(rule)


@router.delete("/{magazine_id}/rule/{rule_id}", status_code=204)
async def delete_rule(
    magazine_id: int,
    rule_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete an include/exclude rule."""
    if not await magazine_service.delete_magazine_rule(db, rule_id):
        raise HTTPException(404, "Rule not found")
    await db.commit()
