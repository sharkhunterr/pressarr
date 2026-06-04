"""Magazine management API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_config, get_db
from app.schemas.magazine import (
    MagazineCreateResource,
    MagazineIdentitySchema,
    MagazinePatternCreateResource,
    MagazinePatternResource,
    MagazinePatternUpdateResource,
    MagazineResource,
    MagazineRuleCreateResource,
    MagazineRuleResource,
    MagazineRuleUpdateResource,
    MagazineStatistics,
    MagazineUpdateResource,
    MetadataSearchResult,
)
from app.services import magazine_service
from app.services.command_service import execute_command, register_command
from app.services.smart_matcher import invalidate_pattern_cache

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
        if stats.get("created"):
            parts.append(f"{stats['created']} issues created")
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
    locale: str | None = Query(
        None,
        min_length=2,
        max_length=2,
        description="ISO-3166 alpha-2 country code; biases ranking toward that country.",
    ),
    status: str | None = Query(
        None,
        pattern="^(ongoing|ceased|all)$",
        description=(
            "Filter results by publication status. ``ongoing`` hides "
            "magazines with a ``ceasedAt`` date, ``ceased`` keeps only "
            "those, ``all`` (default when omitted) keeps everything. "
            "Ongoing entries are always ranked before ceased ones "
            "regardless of this filter."
        ),
    ),
    verified: bool = Query(
        False,
        description=(
            "When true, hide entries that are only attested by a single "
            "national-catalogue source and don't have a Wikidata QID. "
            "Cuts BnF-only / ZDB-only edition records like "
            "``L'Equipe Feder (Montpellier)`` from the result list."
        ),
    ),
    multi_issn: bool = Query(
        False,
        description=(
            "When true, keep only entries whose ISSN Portal record "
            "exposes multiple ISSNs under the same ISSN-L (print + "
            "online + CD-ROM, …). Filters out one-shot serials and "
            "obscure single-edition records."
        ),
    ),
    config=Depends(get_config),
    db: AsyncSession = Depends(get_db),
):
    """Free-text search across the ISSN-first cascade + legacy providers.

    Returns a deduplicated list of candidate magazines ordered by
    title match → ongoing-first → cascade enrichment → alphabetical.
    Each entry's ``sources`` list shows which catalogues contributed.
    """
    return await magazine_service.search_metadata(
        query,
        config,
        db=db,
        locale=locale,
        status=status,
        verified_only=verified,
        multi_issn_only=multi_issn,
    )


@router.get("/identity", response_model=MagazineIdentitySchema)
async def lookup_identity(
    issn: str = Query(
        ...,
        min_length=8,
        max_length=9,
        description="ISSN — eight digits, optional hyphen.",
    ),
    locale: str | None = Query(None, min_length=2, max_length=2),
    db: AsyncSession = Depends(get_db),
):
    """Authoritative ISSN lookup.

    Returns the merged identity from ZDB + Wikidata (+ regional
    providers in phase 3). 404 when no source recognises the ISSN.
    Used by the manual-add flow and by allseerr's dispatcher to
    enrich requests before sending them here.
    """
    identity = await magazine_service.lookup_magazine_by_issn(
        issn, db=db, locale=locale
    )
    if identity is None:
        raise HTTPException(status_code=404, detail="ISSN not found")
    return identity


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




@router.get("/{magazine_id}/rename")
async def preview_rename(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Preview file renames for a magazine (dry run)."""
    from app.models.root_folder import RootFolder
    from app.services.issue_service import rename_issues

    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")

    root_folder = await db.get(RootFolder, magazine.root_folder_id)
    if not root_folder:
        raise HTTPException(404, "Root folder not found")

    naming_template = getattr(config, "naming_template", None)
    if not naming_template:
        from app.services.import_service import DEFAULT_TEMPLATE
        naming_template = DEFAULT_TEMPLATE

    results = await rename_issues(
        db, magazine, naming_template, root_folder.path, preview_only=True,
    )
    return results


@router.post("/{magazine_id}/rename")
async def execute_rename(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Rename all issue files for a magazine according to the naming template."""
    from app.models.root_folder import RootFolder
    from app.services.issue_service import rename_issues

    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")

    root_folder = await db.get(RootFolder, magazine.root_folder_id)
    if not root_folder:
        raise HTTPException(404, "Root folder not found")

    naming_template = getattr(config, "naming_template", None)
    if not naming_template:
        from app.services.import_service import DEFAULT_TEMPLATE
        naming_template = DEFAULT_TEMPLATE

    results = await rename_issues(
        db, magazine, naming_template, root_folder.path, preview_only=False,
    )
    renamed = [r for r in results if r["old_path"] != r["new_path"]]
    return {"renamed": len(renamed), "results": renamed}

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


@router.put(
    "/{magazine_id}/pattern/{pattern_id}",
    response_model=MagazinePatternResource,
)
async def update_pattern(
    magazine_id: int,
    pattern_id: int,
    body: MagazinePatternUpdateResource,
    db: AsyncSession = Depends(get_db),
):
    """Update a naming pattern."""
    pattern = await magazine_service.update_magazine_pattern(
        db, pattern_id, body.model_dump(exclude_none=True)
    )
    if pattern is None:
        raise HTTPException(404, "Pattern not found")
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


@router.post(
    "/{magazine_id}/pattern/{pattern_id}/to-exclude-rule",
    response_model=MagazineRuleResource,
)
async def convert_pattern_to_exclude_rule(
    magazine_id: int,
    pattern_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Convert a pattern to an exclude rule (template-based regex) and delete it."""
    import re as re_mod

    from app.parser.magazine_parser import parse_magazine_filename
    from app.services.smart_matcher import extract_naming_pattern

    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")

    pattern_obj = await magazine_service.get_magazine_pattern(db, pattern_id)
    if pattern_obj is None:
        raise HTTPException(404, "Pattern not found")

    # Convert pattern text → template → regex
    parsed = parse_magazine_filename(pattern_obj.pattern)
    template = extract_naming_pattern(pattern_obj.pattern, parsed)

    if template:
        # Build regex from template (same logic as match_against_pattern)
        regex_str = re_mod.escape(template)
        regex_str = regex_str.replace(re_mod.escape("{number}"), r"\d+")
        regex_str = regex_str.replace(re_mod.escape("{year}"), r"\d{4}")
        regex_str = regex_str.replace(re_mod.escape("{month}"), r"\d{1,2}")
        regex_str = regex_str.replace(re_mod.escape("{day}"), r"\d{1,2}")
    else:
        # No template extraction possible — use escaped literal
        regex_str = re_mod.escape(pattern_obj.pattern)

    # Create exclude rule + delete pattern
    rule = await magazine_service.add_magazine_rule(
        db, magazine_id, {"rule_type": "exclude", "pattern": regex_str}
    )
    await magazine_service.delete_magazine_pattern(db, pattern_id)
    await db.commit()
    invalidate_pattern_cache(magazine_id)
    return MagazineRuleResource.model_validate(rule)


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


@router.put(
    "/{magazine_id}/rule/{rule_id}",
    response_model=MagazineRuleResource,
)
async def update_rule(
    magazine_id: int,
    rule_id: int,
    body: MagazineRuleUpdateResource,
    db: AsyncSession = Depends(get_db),
):
    """Update an include/exclude rule."""
    rule = await magazine_service.update_magazine_rule(
        db, rule_id, body.model_dump(exclude_none=True)
    )
    if rule is None:
        raise HTTPException(404, "Rule not found")
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


# ---------------------------------------------------------------------------
# Scene release scanning (Bookys / telecharger-magazines.org / …)
#
# These endpoints sit between the metadata cascade (which knows
# *what* the magazine is) and the download dispatcher (which
# knows *how* to fetch a file). Each call returns the latest set
# of MagazineRelease rows for the magazine — POST kicks off a
# fresh scrape of every enabled scene indexer; GET reads what's
# already in the DB.
# ---------------------------------------------------------------------------


@router.get("/{magazine_id}/releases", response_model=list[dict])
async def list_releases(
    magazine_id: int,
    source: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return every persisted scene release for a magazine,
    newest-first. Empty list when no scan has run yet (or no
    indexer is enabled). Pass ``?source=bookys`` (or
    ``telecharger_magazines``) to restrict to one indexer —
    the pressarr UI does this so each manual-search tab only
    sees its own rows."""
    from sqlalchemy import select

    from app.models.magazine_release import MagazineRelease
    from app.services.magazine_release_service import serialise_release

    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")
    stmt = (
        select(MagazineRelease)
        .where(MagazineRelease.magazine_id == magazine_id)
        .order_by(MagazineRelease.discovered_at.desc())
    )
    if source:
        stmt = stmt.where(MagazineRelease.source == source)
    rows = (await db.scalars(stmt)).all()
    return [serialise_release(r) for r in rows]


@router.post("/{magazine_id}/releases/scan", response_model=list[dict])
async def scan_releases(
    magazine_id: int,
    source: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Run a fresh scrape against every enabled scene indexer
    and return the resulting release list. Idempotent — runs
    against the same indexers + same title each time and
    upserts on (source, source_url). Pass ``?source=…`` to
    limit the scrape to a single indexer (UI uses this when
    the operator clicks "Scan" inside one tab)."""
    from app.services.magazine_release_service import (
        scan_magazine_releases,
        serialise_release,
    )

    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")
    releases = await scan_magazine_releases(
        magazine, config, db, source=source
    )
    return [serialise_release(r) for r in releases]


@router.post(
    "/{magazine_id}/releases/{release_id}/grab",
    response_model=dict,
)
async def grab_release(
    magazine_id: int,
    release_id: int,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Hand off a scraped release to the configured download
    client (JDownloader 2 folder-watch in v1). Writes a
    ``.crawljob`` file, flips the release's status to
    ``grabbed`` + stamps ``grabbed_at``, returns the updated
    row."""
    from sqlalchemy import select

    from app.models.magazine_release import MagazineRelease
    from app.services.jdownloader_dispatcher import (
        JDownloaderDispatchError,
        dispatch_release,
    )
    from app.services.magazine_release_service import serialise_release

    magazine = await magazine_service.get_magazine(db, magazine_id)
    if magazine is None:
        raise HTTPException(404, "Magazine not found")
    release = await db.scalar(
        select(MagazineRelease).where(
            MagazineRelease.id == release_id,
            MagazineRelease.magazine_id == magazine_id,
        )
    )
    if release is None:
        raise HTTPException(404, "Release not found for this magazine")

    try:
        crawljob_path = dispatch_release(
            release=release, magazine=magazine, config=config
        )
    except JDownloaderDispatchError as e:
        # Persist the failure on the row so the UI can show
        # *why* it didn't dispatch, then surface 502 so the
        # caller knows the action was not retried. Also emit
        # a history event so the operator sees the attempt in
        # the activity log instead of a silent click.
        release.status = "failed"
        release.status_message = str(e)
        from app.services.history_service import create_event as _h

        await _h(
            db,
            event_type="error",
            magazine_id=magazine.id,
            details=f"Scene grab failed: {e!s}",
            data={
                "release_id": release.id,
                "release_title": release.title,
                "source": release.source,
                "reason": str(e),
            },
        )
        await db.commit()
        await db.refresh(release)
        raise HTTPException(status_code=502, detail=str(e)) from e

    # Successful dispatch — record a "grab" event so it shows
    # up in the magazine's history alongside Prowlarr grabs.
    from app.services.history_service import create_event as _h

    await _h(
        db,
        event_type="grab",
        magazine_id=magazine.id,
        details=f"Grabbed (scene): {release.title}",
        data={
            "release_id": release.id,
            "release_title": release.title,
            "source": release.source,
            "source_url": release.source_url,
            "crawljob": crawljob_path.name,
            "hosters": [
                h.get("hoster")
                for h in (release.hoster_links and __import__("json").loads(release.hoster_links) or [])
            ],
        },
    )
    await db.commit()
    await db.refresh(release)
    return serialise_release(release)
