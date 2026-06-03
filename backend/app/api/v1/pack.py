"""Pack management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_config, get_db
from app.schemas.pack import (
    PackCreateResource,
    PackDispatchFileResource,
    PackDispatchPreviewResource,
    PackPatternCreateResource,
    PackPatternResource,
    PackResource,
    PackRuleCreateResource,
    PackRuleResource,
    PackStatistics,
    PackUpdateResource,
)
from app.services import pack_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pack", tags=["Packs"])


# ---- Pack CRUD ----


@router.get("", response_model=list[PackResource])
async def list_packs(
    sort_key: str = Query("name", alias="sortKey"),
    sort_dir: str = Query("asc", alias="sortDir"),
    monitored: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    packs = await pack_service.list_packs(db, sort_key, sort_dir, monitored)
    result = []
    for pack in packs:
        stats = await pack_service.get_statistics(db, pack.id)
        resource = PackResource(
            id=pack.id,
            name=pack.name,
            name_slug=pack.name_slug,
            description=pack.description,
            search_query=pack.search_query,
            recurrence=pack.recurrence,
            auto_search=pack.auto_search,
            auto_grab=pack.auto_grab,
            auto_import=pack.auto_import,
            monitored=pack.monitored,
            quality_profile_id=pack.quality_profile_id,
            root_folder_id=pack.root_folder_id,
            added_at=pack.added_at,
            last_searched_at=pack.last_searched_at,
            patterns=[
                PackPatternResource(
                    id=p.id,
                    pack_id=p.pack_id,
                    pattern=p.pattern,
                    source=p.source,
                    uploader=p.uploader,
                    last_seen_at=p.last_seen_at,
                    created_at=p.created_at,
                )
                for p in pack.patterns
            ],
            rules=[
                PackRuleResource(
                    id=r.id, pack_id=r.pack_id, rule_type=r.rule_type, pattern=r.pattern
                )
                for r in pack.rules
            ],
            statistics=PackStatistics(**stats),
        )
        result.append(resource)
    return result


def _pack_to_resource(pack, stats: dict) -> PackResource:
    return PackResource(
        id=pack.id,
        name=pack.name,
        name_slug=pack.name_slug,
        description=pack.description,
        search_query=pack.search_query,
        recurrence=pack.recurrence,
        auto_search=pack.auto_search,
        auto_grab=pack.auto_grab,
        auto_import=pack.auto_import,
        monitored=pack.monitored,
        quality_profile_id=pack.quality_profile_id,
        root_folder_id=pack.root_folder_id,
        added_at=pack.added_at,
        last_searched_at=pack.last_searched_at,
        patterns=[
            PackPatternResource(
                id=p.id,
                pack_id=p.pack_id,
                pattern=p.pattern,
                source=p.source,
                uploader=p.uploader,
                last_seen_at=p.last_seen_at,
                created_at=p.created_at,
            )
            for p in pack.patterns
        ],
        rules=[
            PackRuleResource(
                id=r.id, pack_id=r.pack_id, rule_type=r.rule_type, pattern=r.pattern
            )
            for r in pack.rules
        ],
        statistics=PackStatistics(**stats),
    )


@router.get("/{pack_id}", response_model=PackResource)
async def get_pack(pack_id: int, db: AsyncSession = Depends(get_db)):
    pack = await pack_service.get_pack(db, pack_id)
    if pack is None:
        raise HTTPException(404, "Pack not found")
    stats = await pack_service.get_statistics(db, pack_id)
    return _pack_to_resource(pack, stats)


@router.post("", response_model=PackResource, status_code=201)
async def create_pack(body: PackCreateResource, db: AsyncSession = Depends(get_db)):
    try:
        pack = await pack_service.create_pack(db, body.model_dump())
        pack_id = pack.id  # save before commit expires attributes
        await db.commit()
        pack = await pack_service.get_pack(db, pack_id)
        stats = await pack_service.get_statistics(db, pack_id)
        return _pack_to_resource(pack, stats)
    except ValueError as e:
        raise HTTPException(409, str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error creating pack")
        raise HTTPException(500, "Failed to create pack")


@router.put("/{pack_id}", response_model=PackResource)
async def update_pack(
    pack_id: int, body: PackUpdateResource, db: AsyncSession = Depends(get_db)
):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    pack = await pack_service.update_pack(db, pack_id, data)
    if pack is None:
        raise HTTPException(404, "Pack not found")
    await db.commit()
    pack = await pack_service.get_pack(db, pack_id)
    stats = await pack_service.get_statistics(db, pack_id)
    return _pack_to_resource(pack, stats)


@router.delete("/{pack_id}", status_code=204)
async def delete_pack(pack_id: int, db: AsyncSession = Depends(get_db)):
    if not await pack_service.delete_pack(db, pack_id):
        raise HTTPException(404, "Pack not found")
    await db.commit()


# ---- Patterns ----


@router.post("/{pack_id}/pattern", response_model=PackPatternResource, status_code=201)
async def add_pattern(
    pack_id: int, body: PackPatternCreateResource, db: AsyncSession = Depends(get_db)
):
    pack = await pack_service.get_pack(db, pack_id)
    if pack is None:
        raise HTTPException(404, "Pack not found")
    pattern = await pack_service.add_pattern(db, pack_id, body.model_dump())
    # Build resource before commit (commit expires attributes)
    resource = PackPatternResource(
        id=pattern.id,
        pack_id=pattern.pack_id,
        pattern=pattern.pattern,
        source=pattern.source,
        uploader=pattern.uploader,
        last_seen_at=pattern.last_seen_at,
        created_at=pattern.created_at,
    )
    await db.commit()
    return resource


@router.delete("/{pack_id}/pattern/{pattern_id}", status_code=204)
async def delete_pattern(
    pack_id: int, pattern_id: int, db: AsyncSession = Depends(get_db)
):
    if not await pack_service.delete_pattern(db, pattern_id):
        raise HTTPException(404, "Pattern not found")
    await db.commit()


# ---- Rules ----


@router.post("/{pack_id}/rule", response_model=PackRuleResource, status_code=201)
async def add_rule(
    pack_id: int, body: PackRuleCreateResource, db: AsyncSession = Depends(get_db)
):
    pack = await pack_service.get_pack(db, pack_id)
    if pack is None:
        raise HTTPException(404, "Pack not found")
    rule = await pack_service.add_rule(db, pack_id, body.model_dump())
    resource = PackRuleResource(
        id=rule.id, pack_id=rule.pack_id, rule_type=rule.rule_type, pattern=rule.pattern
    )
    await db.commit()
    return resource


@router.delete("/{pack_id}/rule/{rule_id}", status_code=204)
async def delete_rule(
    pack_id: int, rule_id: int, db: AsyncSession = Depends(get_db)
):
    if not await pack_service.delete_rule(db, rule_id):
        raise HTTPException(404, "Rule not found")
    await db.commit()


# ---- Grab ----


@router.post("/{pack_id}/grab")
async def grab_pack(
    pack_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Grab a torrent for a pack. Learns the pattern from the torrent title."""
    from app.services.download_service import grab_pack_release

    pack = await pack_service.get_pack(db, pack_id)
    if pack is None:
        raise HTTPException(404, "Pack not found")

    download_url = body.get("downloadUrl")
    title = body.get("title", "")
    protocol = body.get("protocol", "torrent")
    guid = body.get("guid", "")
    indexer = body.get("indexer", "")

    if not download_url:
        raise HTTPException(422, "downloadUrl is required")

    # Learn pattern from this grab
    await pack_service.learn_pattern_from_grab(db, pack_id, title, indexer)

    # Send to download client
    result = await grab_pack_release(db, pack_id, download_url, title, protocol, guid)
    await db.commit()

    return result


# ---- Dispatch ----


@router.post("/{pack_id}/dispatch/preview", response_model=PackDispatchPreviewResource)
async def preview_dispatch(
    pack_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Preview how files from a completed pack download will be dispatched."""
    pack = await pack_service.get_pack(db, pack_id)
    if pack is None:
        raise HTTPException(404, "Pack not found")

    download_id = body.get("downloadId", "")

    # Resolve files from download client
    from app.services.download_service import _resolve_download_path

    save_path = await _resolve_download_path(db, download_id)
    if not save_path:
        raise HTTPException(404, f"Download {download_id} not found or path unavailable")

    files = pack_service.collect_pack_files(save_path)
    if not files:
        raise HTTPException(404, "No supported files found in download")

    files_preview = await pack_service.preview_dispatch(db, pack_id, files, pack.rules)
    matched = sum(1 for f in files_preview if f["matched_magazine_id"])
    excluded = sum(1 for f in files_preview if f["excluded"])

    return PackDispatchPreviewResource(
        pack_id=pack_id,
        download_id=download_id,
        torrent_name=save_path.name,
        files=[PackDispatchFileResource(**f) for f in files_preview],
        total_files=len(files_preview),
        matched_files=matched,
        excluded_files=excluded,
        unmatched_files=len(files_preview) - matched - excluded,
    )


@router.post("/{pack_id}/dispatch/execute")
async def execute_dispatch(
    pack_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Execute file dispatch using user-confirmed assignments."""
    pack = await pack_service.get_pack(db, pack_id)
    if pack is None:
        raise HTTPException(404, "Pack not found")

    download_id = body.get("downloadId", "")
    assignments = body.get("assignments", [])

    from app.services.download_service import (
        _grab_registry,
        _processed_downloads,
        _resolve_download_path,
        _save_registry,
    )

    save_path = await _resolve_download_path(db, download_id)
    if not save_path:
        raise HTTPException(404, f"Download {download_id} not found")

    files = pack_service.collect_pack_files(save_path)
    file_paths_by_name = {f.name: f for f in files}

    results = await pack_service.dispatch_files(db, assignments, file_paths_by_name, config)
    await db.commit()

    imported = sum(1 for r in results if r.get("success"))

    # Create history event
    from app.services.history_service import create_event

    await create_event(
        db,
        event_type="import",
        pack_id=pack_id,
        details=f"Pack dispatch: {imported}/{len(results)} files imported",
        data={
            "pack_name": pack.name,
            "total_files": len(results),
            "imported_files": imported,
        },
    )
    await db.commit()

    # Mark download as processed
    _processed_downloads.add(download_id)
    _grab_registry.pop(download_id, None)
    _save_registry()

    # Notify frontend
    try:
        from app.api.v1.websocket import manager as ws_manager

        await ws_manager.broadcast("library:updated", {})
    except Exception:
        pass

    return {"results": results, "imported": imported, "total": len(results)}
