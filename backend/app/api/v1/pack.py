"""Pack management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_config, get_db
from app.schemas.pack import (
    PackCreateResource,
    PackDispatchFileResource,
    PackDispatchMetadataUpdate,
    PackDispatchResolveRequest,
    PackPatternCreateResource,
    PackPatternResource,
    PackResource,
    PackRuleCreateResource,
    PackRuleResource,
    PackStatistics,
    PackUpdateResource,
)
from app.services import pack_dispatch_service, pack_service

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
        result.append(_pack_to_resource(pack, stats))
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
        deep_ai_analysis=pack.deep_ai_analysis,
        auto_create_missing_magazines=pack.auto_create_missing_magazines,
        preview_before_import=pack.preview_before_import,
        default_new_magazine_frequency=pack.default_new_magazine_frequency,
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


# ---- Dispatch (new pipeline via pack_dispatch_service) ----


def _dispatch_row_to_resource(row) -> PackDispatchFileResource:
    """Sérialise un ``PackDispatchFile`` pour l'API."""
    import json as _json

    extracted = None
    if row.extracted_metadata:
        try:
            extracted = _json.loads(row.extracted_metadata)
        except Exception:
            extracted = None
    proposed = None
    if row.proposed_magazine_data:
        try:
            proposed = _json.loads(row.proposed_magazine_data)
        except Exception:
            proposed = None
    matched_title = None
    if row.matched_magazine is not None:
        matched_title = row.matched_magazine.title
    return PackDispatchFileResource(
        id=row.id,
        pack_id=row.pack_id,
        download_id=row.download_id,
        filename=row.filename,
        path=row.path,
        size=row.size,
        status=row.status,
        error_message=row.error_message,
        ai_run_id=row.ai_run_id,
        extracted_metadata=extracted,
        matched_magazine_id=row.matched_magazine_id,
        matched_magazine_title=matched_title,
        match_score=row.match_score,
        match_source=row.match_source,
        confidence=row.confidence,
        proposed_magazine_data=proposed,
        user_action=row.user_action,
        user_action_magazine_id=row.user_action_magazine_id,
        resolved_issue_id=row.resolved_issue_id,
        created_at=row.created_at,
        analyzed_at=row.analyzed_at,
        resolved_at=row.resolved_at,
    )


@router.get("/{pack_id}/dispatch", response_model=list[PackDispatchFileResource])
async def list_dispatch(
    pack_id: int,
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Liste des fichiers de dispatch (analysés / pending / imported / …).
    Alimente l'onglet Dispatch de PackDetail."""
    from sqlalchemy.orm import selectinload

    from app.models.pack_dispatch_file import PackDispatchFile as _PDF
    from sqlalchemy import select as _select

    stmt = (
        _select(_PDF)
        .options(selectinload(_PDF.matched_magazine))
        .where(_PDF.pack_id == pack_id)
    )
    if status:
        stmt = stmt.where(_PDF.status == status)
    stmt = stmt.order_by(_PDF.created_at.desc())
    rows = list((await db.execute(stmt)).scalars().all())
    return [_dispatch_row_to_resource(r) for r in rows]


@router.post(
    "/{pack_id}/dispatch/{file_id}/resolve",
    response_model=PackDispatchFileResource,
)
async def resolve_dispatch(
    pack_id: int,
    file_id: int,
    body: PackDispatchResolveRequest,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Applique l'action utilisateur sur un fichier pending_user :
    assign_existing / create_magazine / ignore."""
    try:
        row = await pack_dispatch_service.resolve_dispatch_file(
            db,
            file_id=file_id,
            action=body.action,
            magazine_id=body.magazine_id,
            magazine_data=body.magazine_data,
            metadata_overrides=body.metadata_overrides,
            config=config,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e
    # Re-fetch avec relations
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select as _select
    from app.models.pack_dispatch_file import PackDispatchFile as _PDF
    row = (
        await db.execute(
            _select(_PDF)
            .options(selectinload(_PDF.matched_magazine))
            .where(_PDF.id == file_id)
        )
    ).scalar_one()
    return _dispatch_row_to_resource(row)


@router.patch(
    "/{pack_id}/dispatch/{file_id}",
    response_model=PackDispatchFileResource,
)
async def update_dispatch_metadata(
    pack_id: int,
    file_id: int,
    body: PackDispatchMetadataUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Édition manuelle des metadata extraites (title, N°, date, ISSN).
    Utile quand l'IA a mal détecté et que l'utilisateur veut corriger
    avant de valider (assign/create)."""
    overrides = body.model_dump(exclude_none=True)
    if not overrides:
        raise HTTPException(400, "no fields to update")
    try:
        await pack_dispatch_service.update_dispatch_metadata(
            db, file_id=file_id, overrides=overrides,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select as _select
    from app.models.pack_dispatch_file import PackDispatchFile as _PDF
    row = (
        await db.execute(
            _select(_PDF)
            .options(selectinload(_PDF.matched_magazine))
            .where(_PDF.id == file_id)
        )
    ).scalar_one()
    return _dispatch_row_to_resource(row)


@router.post(
    "/{pack_id}/dispatch/{file_id}/reanalyze",
    response_model=PackDispatchFileResource,
)
async def reanalyze_dispatch(
    pack_id: int,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Relance l'analyse IA sur un fichier — utile après ajustement des
    zones de crop / changement de modèle."""
    from app.database import async_session_factory
    try:
        await pack_dispatch_service.reanalyze_dispatch_file(
            db,
            file_id=file_id,
            config=config,
            session_factory=async_session_factory,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select as _select
    from app.models.pack_dispatch_file import PackDispatchFile as _PDF
    row = (
        await db.execute(
            _select(_PDF)
            .options(selectinload(_PDF.matched_magazine))
            .where(_PDF.id == file_id)
        )
    ).scalar_one()
    return _dispatch_row_to_resource(row)


@router.post("/{pack_id}/dispatch/rescan-imported")
async def rescan_imported_dispatch(
    pack_id: int,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Re-analyse IA sur TOUS les fichiers "imported" du pack.

    Cas d'usage : les imports initiaux ont produit des metadata
    erronées (mauvais titre / date). L'utilisateur veut re-scanner
    d'un coup pour voir où sont les erreurs et corriger via l'UI.

    N'écrase pas l'import réel — seuls extracted_metadata + confidence
    sont mis à jour. Retourne stats {total, reanalyzed, errors}.
    """
    from app.database import async_session_factory
    return await pack_dispatch_service.rescan_imported(
        db, pack_id, config=config, session_factory=async_session_factory,
    )


@router.delete("/{pack_id}/dispatch/{file_id}", status_code=204)
async def delete_dispatch(
    pack_id: int,
    file_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retire une row dispatch (le fichier reste sur disque)."""
    ok = await pack_dispatch_service.delete_dispatch_file(db, file_id)
    if not ok:
        raise HTTPException(404, "Dispatch file not found")


# ─── Anciens endpoints (compat) — supprimés ────────────────────────────
# Les routes suivantes sont retirées car remplacées par le nouveau
# pipeline persistent :
#   POST /pack/{id}/dispatch/preview   → GET /pack/{id}/dispatch
#   POST /pack/{id}/dispatch/execute   → POST /pack/{id}/dispatch/{file_id}/resolve
#   POST /pack/{id}/reimport           → POST /pack/{id}/dispatch/{file_id}/resolve
#   GET  /pack/{id}/pending-files      → GET /pack/{id}/dispatch?status=pending_user


