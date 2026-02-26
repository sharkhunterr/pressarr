"""Search API endpoints."""
import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_config, get_db
from app.schemas import CamelModel
from app.schemas.search import GrabResponse, SearchResultResource
from app.services import search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


@router.get("", response_model=list[SearchResultResource])
async def search(
    issue_id: int | None = Query(None, alias="issueId"),
    magazine_id: int | None = Query(None, alias="magazineId"),
    query: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    if issue_id:
        return await search_service.search_issue(db, issue_id, config)
    elif magazine_id:
        results_by_issue = await search_service.search_magazine_missing(db, magazine_id, config)
        # Flatten all results
        all_results = []
        for issue_results in results_by_issue.values():
            all_results.extend(issue_results)
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results
    elif query:
        # Free search - not tied to a specific issue
        return []
    raise HTTPException(422, "Provide issueId, magazineId, or query")


@router.post("/grab", response_model=GrabResponse)
async def grab_release(
    body: dict,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    issue_id = body.get("issueId")
    download_url = body.get("downloadUrl")
    title = body.get("title", "")
    protocol = body.get("protocol", "torrent")
    guid = body.get("guid", "")

    if not issue_id or not download_url:
        raise HTTPException(422, "issueId and downloadUrl are required")

    from app.services.download_service import grab_release as do_grab
    result = await do_grab(db, issue_id, download_url, title, protocol, guid)
    return result


# ---- Internet Archive endpoints ----------------------------------------


@router.get("/internetarchive", response_model=list[SearchResultResource])
async def search_internet_archive(
    query: str = Query(...),
    magazine_id: int | None = Query(None, alias="magazineId"),
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Search the Internet Archive for magazine issues."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {
                "q": f'collection:magazine_rack "{query}"',
                "fl[]": ["identifier", "title", "date", "format", "downloads"],
                "rows": 50,
                "output": "json",
            }
            resp = await client.get(
                "https://archive.org/advancedsearch.php", params=params
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("IA search failed: %s", e)
        raise HTTPException(502, f"Internet Archive search failed: {e}")

    docs = data.get("response", {}).get("docs", [])

    results: list[SearchResultResource] = []
    for doc in docs:
        identifier = doc.get("identifier", "")
        title = doc.get("title", identifier)
        formats = doc.get("format", [])
        if isinstance(formats, str):
            formats = [formats]

        results.append(SearchResultResource(
            guid=identifier,
            title=title,
            indexer="Internet Archive",
            size=0,
            age=0,
            protocol="ia",
            seeders=doc.get("downloads"),
            quality="unknown",
            language="unknown",
            score=0.0,
            is_blocklisted=False,
            download_url=f"https://archive.org/download/{identifier}",
        ))

    # If magazine_id is provided, run matching logic
    if magazine_id and results:
        from app.services.search_service import match_ia_results
        results = await match_ia_results(db, results, magazine_id)

    return results


class IADownloadRequest(CamelModel):
    identifier: str
    filename: str = ""
    issue_id: int | None = None
    magazine_id: int | None = None
    preferred_format: str = "pdf"


# Priority order for downloadable formats
_FORMAT_PRIORITY = [".pdf", ".cbz", ".cbr", ".epub"]


async def _resolve_ia_filename(identifier: str, preferred_format: str = "pdf") -> str:
    """Fetch IA item metadata and find the best downloadable file.

    The filename provided by the frontend is typically wrong (it just
    appends '.pdf' to the identifier). We need to look up the actual
    files inside the item and pick the best one.
    """
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"https://archive.org/metadata/{identifier}/files")
        resp.raise_for_status()
        files = resp.json().get("result", [])

    # Build a dict of extension -> best filename (largest file wins for ties)
    candidates: dict[str, tuple[str, int]] = {}
    for f in files:
        name = f.get("name", "")
        lower = name.lower()
        size = int(f.get("size", 0) or 0)
        for ext in _FORMAT_PRIORITY:
            if lower.endswith(ext):
                if ext not in candidates or size > candidates[ext][1]:
                    candidates[ext] = (name, size)
                break

    if not candidates:
        raise ValueError(f"No downloadable file found in IA item '{identifier}'")

    # Pick by priority, favouring preferred_format
    preferred_ext = f".{preferred_format.lstrip('.')}"
    if preferred_ext in candidates:
        return candidates[preferred_ext][0]
    for ext in _FORMAT_PRIORITY:
        if ext in candidates:
            return candidates[ext][0]

    # Shouldn't reach here given the check above
    raise ValueError(f"No downloadable file found in IA item '{identifier}'")


async def _run_import(
    file_path: Path,
    issue_id: int | None,
    config,
    magazine_id: int | None = None,
) -> dict:
    """Run file import in a fresh DB session.

    Uses direct issue import when issue_id is provided,
    falls back to filename-based matching otherwise (with optional magazine_id
    to bypass fuzzy title matching).
    """
    import app.database as db_module

    logger.info(
        "[_run_import] START file_path=%s, issue_id=%s, magazine_id=%s, file_exists=%s",
        file_path, issue_id, magazine_id, file_path.exists(),
    )

    async with db_module.async_session_factory() as db:
        logger.info("[_run_import] Fresh DB session created")
        try:
            if issue_id:
                logger.info("[_run_import] Using import_file_for_issue (issue_id=%s)", issue_id)
                from app.services.import_service import (
                    import_file_for_issue,
                )
                result = await import_file_for_issue(
                    db, file_path, issue_id, config
                )
                logger.info("[_run_import] import_file_for_issue returned: %s", result)
                if result.get("success"):
                    await db.commit()
                    logger.info("[_run_import] DB committed OK")
                    return result
                logger.warning("[_run_import] import_file_for_issue not successful, falling through to process_downloaded_file")
            # Fallback to generic filename-based import (with magazine_id hint)
            logger.info("[_run_import] Using process_downloaded_file (fallback, magazine_id=%s)", magazine_id)
            from app.services.import_service import (
                process_downloaded_file,
            )
            result = await process_downloaded_file(
                db, file_path, config, magazine_id=magazine_id
            )
            logger.info("[_run_import] process_downloaded_file returned: %s", result)
            await db.commit()
            logger.info("[_run_import] DB committed OK")
            return result
        except Exception as e:
            logger.error("[_run_import] EXCEPTION: %s", e, exc_info=True)
            await db.rollback()
            raise


async def _lookup_issue_info(
    db: AsyncSession, issue_id: int | None,
) -> tuple[int | None, str | None, int | None]:
    """Look up magazine_id, magazine_title, issue_number for queue display."""
    if not issue_id:
        return None, None, None
    from sqlalchemy import select
    from app.models.issue import Issue
    from app.models.magazine import Magazine

    result = await db.execute(
        select(Issue.magazine_id, Issue.number, Magazine.title)
        .join(Magazine, Issue.magazine_id == Magazine.id)
        .where(Issue.id == issue_id)
    )
    row = result.first()
    if not row:
        return None, None, None
    return row[0], row[2], row[1]  # magazine_id, magazine_title, issue_number


@router.post("/internetarchive/download", response_model=GrabResponse)
async def download_from_internet_archive(
    body: IADownloadRequest,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Download a specific file from the Internet Archive (async background)."""
    from app.services.direct_download_tracker import tracker

    if not body.identifier:
        raise HTTPException(422, "identifier is required")

    # Auto-resolve the actual filename from IA metadata
    try:
        filename = await _resolve_ia_filename(
            body.identifier, body.preferred_format
        )
        logger.info("[IA download] Resolved filename: %s", filename)
    except Exception as e:
        raise HTTPException(
            502,
            f"Could not find downloadable file in "
            f"'{body.identifier}': {e}",
        )

    download_id = f"{body.identifier}/{filename}"

    # Check if already in progress
    existing = tracker.get(download_id)
    if existing and existing.status.status in ("queued", "downloading", "importing"):
        return GrabResponse(
            issue_id=body.issue_id or 0,
            download_id=download_id,
            message=f"Already in progress: {filename}",
        )

    download_dir = str(
        Path(getattr(config, "download_path", "/tmp/pressarr_downloads")) / "ia"
    )

    # Look up issue info for queue display
    magazine_id, magazine_title, issue_number = await _lookup_issue_info(
        db, body.issue_id
    )
    # Use body.magazine_id as fallback (Manual Research modal)
    if not magazine_id and body.magazine_id:
        magazine_id = body.magazine_id
        from sqlalchemy import select as sa_select
        from app.models.magazine import Magazine
        mag_result = await db.execute(
            sa_select(Magazine.title).where(Magazine.id == body.magazine_id)
        )
        row = mag_result.first()
        if row:
            magazine_title = row[0]

    # Register in tracker
    tracked = tracker.register(
        download_id=download_id,
        name=filename,
        protocol="ia",
        source="Internet Archive",
        issue_id=body.issue_id,
        magazine_id=magazine_id,
        magazine_title=magazine_title,
        issue_number=issue_number,
    )

    # Launch background task
    task = asyncio.create_task(
        _ia_download_task(
            download_id, body.identifier, filename,
            download_dir, body.issue_id, magazine_id, config,
        )
    )
    tracked.task = task

    # Notify frontend
    from app.api.v1.websocket import manager
    await manager.broadcast("queue:added", {})

    return GrabResponse(
        issue_id=body.issue_id or 0,
        download_id=download_id,
        message=f"Queued download: {filename}",
    )


async def _create_history_event(
    event_type: str,
    issue_id: int | None = None,
    magazine_id: int | None = None,
    details: str = "",
) -> None:
    """Create a history event in a fresh DB session (for background tasks)."""
    import app.database as db_module

    try:
        async with db_module.async_session_factory() as db:
            from app.services.history_service import create_event
            await create_event(
                db,
                event_type=event_type,
                magazine_id=magazine_id,
                issue_id=issue_id,
                details=details,
            )
            await db.commit()
            logger.info("[history event] Created %s (issue=%s, mag=%s)", event_type, issue_id, magazine_id)
    except Exception:
        logger.warning("[history event] Failed to create %s event", event_type, exc_info=True)


async def _create_grab_event(
    issue_id: int | None,
    magazine_id: int | None,
    source: str,
    title: str,
) -> None:
    """Create a 'grab' history event and set issue status to 'snatched'.

    Uses a fresh DB session since this runs in a background task.
    """
    import app.database as db_module

    try:
        async with db_module.async_session_factory() as db:
            from app.services.history_service import create_event

            # If we have an issue_id, set its status to "snatched"
            if issue_id:
                from sqlalchemy import select as sa_select
                from app.models.issue import Issue

                result = await db.execute(
                    sa_select(Issue).where(Issue.id == issue_id)
                )
                issue = result.scalars().first()
                if issue:
                    issue.status = "snatched"
                    if not magazine_id:
                        magazine_id = issue.magazine_id

            await create_event(
                db,
                event_type="grab",
                magazine_id=magazine_id,
                issue_id=issue_id,
                details=f"Grabbed from {source}: {title}",
            )
            await db.commit()
            logger.info("[grab event] Created for %s (issue=%s, mag=%s)", source, issue_id, magazine_id)
    except Exception:
        logger.warning("[grab event] Failed to create grab event", exc_info=True)


async def _ia_download_task(
    download_id: str,
    identifier: str,
    filename: str,
    download_dir: str,
    issue_id: int | None,
    magazine_id: int | None,
    config,
) -> None:
    """Background task: download from Internet Archive + import."""
    from app.download_clients.internet_archive import InternetArchiveClient
    from app.services.direct_download_tracker import tracker
    from app.api.v1.websocket import manager

    ia_client = InternetArchiveClient()

    # Ensure download directory exists (fixes errno 20 ENOTDIR)
    Path(download_dir).mkdir(parents=True, exist_ok=True)

    # Create "grab" history event + set issue status to "snatched"
    await _create_grab_event(
        issue_id=issue_id,
        magazine_id=magazine_id,
        source="Internet Archive",
        title=filename,
    )

    async def _monitor():
        """Poll client progress and update tracker every 2s."""
        try:
            while True:
                await asyncio.sleep(2)
                status = await ia_client.get_status(download_id)
                if status:
                    tracker.update_status(
                        download_id,
                        progress=status.progress,
                        size=status.size,
                        speed=status.speed,
                        eta=status.eta,
                        name=status.name,
                        save_path=status.save_path,
                    )
        except asyncio.CancelledError:
            pass

    monitor = asyncio.create_task(_monitor())

    try:
        tracker.update_status(download_id, status="downloading")
        logger.info("[IA bg] Starting download: %s/%s", identifier, filename)

        local_path = await ia_client.download(identifier, filename, download_dir)
        monitor.cancel()

        logger.info("[IA bg] Download complete, starting import: %s", local_path)

        # Create "download_completed" history event
        await _create_history_event(
            event_type="download_completed",
            issue_id=issue_id,
            magazine_id=magazine_id,
            details=f"Downloaded from Internet Archive: {filename}",
        )

        tracker.update_status(
            download_id, status="importing", progress=1.0,
            speed=0, eta=0, save_path=str(local_path),
        )
        await manager.broadcast("queue:added", {})

        result = await _run_import(
            Path(local_path), issue_id, config, magazine_id=magazine_id
        )

        if result.get("success"):
            tracker.update_status(download_id, status="imported")
            logger.info("[IA bg] Import succeeded: %s", download_id)
        else:
            error_msg = result.get("message", "Import failed")
            tracker.update_status(download_id, status="failed", error_message=error_msg)
            logger.warning("[IA bg] Import failed: %s -> %s", download_id, error_msg)
            await _create_history_event(
                event_type="error",
                issue_id=issue_id,
                magazine_id=magazine_id,
                details=f"Import failed: {error_msg}",
            )

        await manager.broadcast("queue:added", {})
        # Notify frontend to refresh library/issue data
        await manager.broadcast("library:updated", {"magazineId": magazine_id})

    except asyncio.CancelledError:
        tracker.update_status(download_id, status="failed", error_message="Cancelled")
        logger.info("[IA bg] Cancelled: %s", download_id)
    except Exception as e:
        monitor.cancel()
        logger.error("[IA bg] Failed: %s: %s", download_id, e, exc_info=True)
        tracker.update_status(download_id, status="failed", error_message=str(e))
        await _create_history_event(
            event_type="error",
            issue_id=issue_id,
            magazine_id=magazine_id,
            details=f"Download failed: {e}",
        )
        await manager.broadcast("queue:added", {})
    finally:
        monitor.cancel()
        await ia_client.close()


# ---- Anna's Archive endpoints ------------------------------------------


@router.get("/annasarchive", response_model=list[SearchResultResource])
async def search_annas_archive(
    query: str = Query(...),
    magazine_id: int | None = Query(None, alias="magazineId"),
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Search Anna's Archive for magazine issues."""
    from app.metadata.annas_archive import AnnasArchiveProvider

    mirror = getattr(config, "annas_archive_mirror", "annas-archive.li")
    provider = AnnasArchiveProvider(mirror=mirror)

    try:
        raw_results = await provider.search(query)
    except Exception as e:
        logger.warning("AA search failed: %s", e)
        raise HTTPException(502, f"Anna's Archive search failed: {e}")
    finally:
        await provider.close()

    results: list[SearchResultResource] = []
    for item in raw_results:
        # Parse size string to bytes
        size_bytes = _parse_size(item.get("size", ""))

        results.append(SearchResultResource(
            guid=item["md5"],
            title=item.get("title", item["md5"]),
            indexer="Anna's Archive",
            size=size_bytes,
            age=0,
            protocol="aa",
            seeders=None,
            quality=item.get("format", "pdf"),
            language=item.get("language", "unknown"),
            score=0.0,
            is_blocklisted=False,
            download_url=item.get("url", ""),
        ))

    # If magazine_id is provided, run matching logic
    if magazine_id and results:
        from app.services.search_service import match_ia_results
        results = await match_ia_results(db, results, magazine_id)

    return results


def _parse_size(size_str: str) -> int:
    """Parse a human-readable size string like '45.2MB' into bytes."""
    import re

    if not size_str:
        return 0
    pattern = r"([\d.]+)\s*(kb|mb|gb|tb|bytes?)"
    match = re.match(pattern, size_str.strip(), re.IGNORECASE)
    if not match:
        return 0
    value = float(match.group(1))
    unit = match.group(2).lower()
    multipliers = {
        "bytes": 1, "byte": 1, "kb": 1024,
        "mb": 1024**2, "gb": 1024**3, "tb": 1024**4,
    }
    return int(value * multipliers.get(unit, 1))


class AADownloadRequest(CamelModel):
    md5: str
    issue_id: int | None = None
    magazine_id: int | None = None
    preferred_format: str = "pdf"


@router.post("/annasarchive/download", response_model=GrabResponse)
async def download_from_annas_archive(
    body: AADownloadRequest,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Download a file from Anna's Archive by MD5 hash (async background)."""
    from app.services.direct_download_tracker import tracker

    if not body.md5:
        raise HTTPException(422, "md5 is required")

    download_id = f"aa:{body.md5}"

    # Check if already in progress
    existing = tracker.get(download_id)
    if existing and existing.status.status in ("queued", "downloading", "importing"):
        return GrabResponse(
            issue_id=body.issue_id or 0,
            download_id=download_id,
            message=f"Already in progress: {body.md5}",
        )

    mirror = getattr(config, "annas_archive_mirror", "annas-archive.li")
    download_dir = str(
        Path(getattr(config, "download_path", "/tmp/pressarr_downloads")) / "aa"
    )

    # Look up issue info for queue display
    magazine_id, magazine_title, issue_number = await _lookup_issue_info(
        db, body.issue_id
    )
    # Use body.magazine_id as fallback (Manual Research modal)
    if not magazine_id and body.magazine_id:
        magazine_id = body.magazine_id
        from sqlalchemy import select as sa_select
        from app.models.magazine import Magazine
        mag_result = await db.execute(
            sa_select(Magazine.title).where(Magazine.id == body.magazine_id)
        )
        row = mag_result.first()
        if row:
            magazine_title = row[0]

    # Register in tracker
    tracked = tracker.register(
        download_id=download_id,
        name=f"{body.md5}.pdf",
        protocol="aa",
        source="Anna's Archive",
        issue_id=body.issue_id,
        magazine_id=magazine_id,
        magazine_title=magazine_title,
        issue_number=issue_number,
    )

    # Launch background task
    task = asyncio.create_task(
        _aa_download_task(
            download_id, body.md5, download_dir,
            body.issue_id, magazine_id, mirror, config,
        )
    )
    tracked.task = task

    # Notify frontend
    from app.api.v1.websocket import manager
    await manager.broadcast("queue:added", {})

    return GrabResponse(
        issue_id=body.issue_id or 0,
        download_id=download_id,
        message=f"Queued download: {body.md5}",
    )


async def _aa_download_task(
    download_id: str,
    md5: str,
    download_dir: str,
    issue_id: int | None,
    magazine_id: int | None,
    mirror: str,
    config,
) -> None:
    """Background task: download from Anna's Archive + import."""
    from app.download_clients.annas_archive import AnnasArchiveClient
    from app.services.direct_download_tracker import tracker
    from app.api.v1.websocket import manager

    aa_client = AnnasArchiveClient(mirror=mirror)

    # Ensure download directory exists (fixes errno 20 ENOTDIR)
    Path(download_dir).mkdir(parents=True, exist_ok=True)

    # Create "grab" history event + set issue status to "snatched"
    await _create_grab_event(
        issue_id=issue_id,
        magazine_id=magazine_id,
        source="Anna's Archive",
        title=md5,
    )

    async def _monitor():
        """Poll client progress and update tracker every 2s."""
        try:
            while True:
                await asyncio.sleep(2)
                status = await aa_client.get_status(download_id)
                if status:
                    tracker.update_status(
                        download_id,
                        progress=status.progress,
                        size=status.size,
                        speed=status.speed,
                        eta=status.eta,
                        name=status.name,
                        save_path=status.save_path,
                    )
        except asyncio.CancelledError:
            pass

    monitor = asyncio.create_task(_monitor())

    try:
        tracker.update_status(download_id, status="downloading")
        logger.info("[AA bg] Starting download: md5=%s", md5)

        local_path = await aa_client.download(md5, download_dir)
        monitor.cancel()

        logger.info("[AA bg] Download complete, starting import: %s", local_path)

        # Create "download_completed" history event
        await _create_history_event(
            event_type="download_completed",
            issue_id=issue_id,
            magazine_id=magazine_id,
            details=f"Downloaded from Anna's Archive: {md5}",
        )

        tracker.update_status(
            download_id, status="importing", progress=1.0,
            speed=0, eta=0, save_path=str(local_path),
        )
        await manager.broadcast("queue:added", {})

        result = await _run_import(
            Path(local_path), issue_id, config, magazine_id=magazine_id
        )

        if result.get("success"):
            tracker.update_status(download_id, status="imported")
            logger.info("[AA bg] Import succeeded: %s", download_id)
        else:
            error_msg = result.get("message", "Import failed")
            tracker.update_status(download_id, status="failed", error_message=error_msg)
            logger.warning("[AA bg] Import failed: %s -> %s", download_id, error_msg)
            await _create_history_event(
                event_type="error",
                issue_id=issue_id,
                magazine_id=magazine_id,
                details=f"Import failed: {error_msg}",
            )

        await manager.broadcast("queue:added", {})
        # Notify frontend to refresh library/issue data
        await manager.broadcast("library:updated", {"magazineId": magazine_id})

    except asyncio.CancelledError:
        tracker.update_status(download_id, status="failed", error_message="Cancelled")
        logger.info("[AA bg] Cancelled: %s", download_id)
    except Exception as e:
        monitor.cancel()
        logger.error("[AA bg] Failed: %s: %s", download_id, e, exc_info=True)
        tracker.update_status(download_id, status="failed", error_message=str(e))
        await _create_history_event(
            event_type="error",
            issue_id=issue_id,
            magazine_id=magazine_id,
            details=f"Download failed: {e}",
        )
        await manager.broadcast("queue:added", {})
    finally:
        monitor.cancel()
        await aa_client.close()
