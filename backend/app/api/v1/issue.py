"""Issue management API endpoints."""

import io
import logging
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.issue import (
    IssueBatchMonitorRequest,
    IssueResource,
    IssueUpdateRequest,
)
from app.services import issue_service
from app.services.command_service import execute_command, register_command

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/issue", tags=["Issues"])


async def _handle_refresh_issue(issue_id: int) -> str | None:
    """Command handler for RefreshIssue."""
    from app.database import async_session_factory

    if async_session_factory is None:
        return "Database not initialized"

    async with async_session_factory() as session:
        result = await issue_service.refresh_issue_metadata(session, issue_id)
        await session.commit()
        return result


register_command("RefreshIssue", _handle_refresh_issue)


@router.get("", response_model=list[IssueResource])
async def list_issues(
    magazine_id: int | None = Query(None, alias="magazineId"),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List issues with optional filters."""
    issues = await issue_service.list_issues(db, magazine_id=magazine_id, status=status)
    return issues


# Batch monitor MUST be declared before /{issue_id} routes
@router.put("/monitor", response_model=list[IssueResource])
async def batch_monitor(
    body: IssueBatchMonitorRequest,
    db: AsyncSession = Depends(get_db),
):
    """Batch update monitoring for multiple issues."""
    updated = []
    for iid in body.issue_ids:
        issue = await issue_service.update_issue_monitored(db, iid, body.monitored)
        if issue:
            updated.append(issue)
    return updated


@router.get("/{issue_id}", response_model=IssueResource)
async def get_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single issue by ID."""
    issue = await issue_service.get_issue(db, issue_id)
    if issue is None:
        raise HTTPException(404, "Issue not found")
    return issue


@router.put("/{issue_id}", response_model=IssueResource)
async def update_issue(
    issue_id: int,
    body: IssueUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update issue fields. Only provided (non-null) fields are updated."""
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(422, "No fields to update")
    if "status" in data:
        allowed = {"wanted", "missing", "available", "snatched"}
        if data["status"] not in allowed:
            raise HTTPException(422, f"Invalid status. Allowed: {', '.join(sorted(allowed))}")
    issue = await issue_service.update_issue(db, issue_id, data)
    if issue is None:
        raise HTTPException(404, "Issue not found")
    return issue


@router.delete("/{issue_id}")
async def delete_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete an issue and its associated file entirely."""
    deleted = await issue_service.delete_issue(db, issue_id)
    if not deleted:
        raise HTTPException(404, "Issue not found")
    return {}


@router.delete("/{issue_id}/file")
async def delete_issue_file(
    issue_id: int,
    unmonitor: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Delete the file associated with an issue.

    When unmonitor=true, also sets the issue as unmonitored.
    """
    deleted = await issue_service.delete_issue_file(db, issue_id, unmonitor=unmonitor)
    if not deleted:
        raise HTTPException(404, "Issue or file not found")
    return {}


@router.get("/{issue_id}/file")
async def download_issue_file(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Download the file associated with an issue."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.issue import Issue

    result = await db.execute(
        select(Issue).options(selectinload(Issue.file)).where(Issue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue or not issue.file:
        raise HTTPException(404, "Issue or file not found")

    file_path = Path(issue.file.path)
    if not file_path.is_file():
        raise HTTPException(404, "File not found on disk")

    filename = issue.file.original_filename or file_path.name
    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/{issue_id}/cover")
async def get_issue_cover(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Serve the issue cover image."""
    issue = await issue_service.get_issue(db, issue_id)
    if issue is None:
        raise HTTPException(404, "Issue not found")

    if not issue.cover_path:
        raise HTTPException(404, "No cover available")

    cover_path = Path(issue.cover_path)
    if not cover_path.is_file():
        raise HTTPException(404, "Cover file not found on disk")

    return FileResponse(cover_path)


@router.post("/{issue_id}/import", status_code=200)
async def import_issue_download(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger import for a snatched issue's download."""
    from app.services.download_service import find_download_ids_for_issue, trigger_import

    issue = await issue_service.get_issue(db, issue_id)
    if issue is None:
        raise HTTPException(404, "Issue not found")

    download_ids = find_download_ids_for_issue(issue_id)
    if not download_ids:
        raise HTTPException(404, "No download found for this issue in the grab registry")

    # Try each registered download (usually just one)
    for download_id in download_ids:
        result = await trigger_import(
            db, download_id,
            issue_id=issue_id,
            magazine_id=issue.magazine_id,
        )
        if result.get("success"):
            return result

    return result  # Return last result even if failed


@router.post("/{issue_id}/refresh", status_code=200)
async def refresh_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a RefreshIssue command."""
    issue = await issue_service.get_issue(db, issue_id)
    if issue is None:
        raise HTTPException(404, "Issue not found")

    command = await execute_command(
        "RefreshIssue",
        body={"issue_id": issue_id},
    )
    return command


# ---------------------------------------------------------------------------
# Issue viewer (page extraction)
# ---------------------------------------------------------------------------

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def _get_issue_file_path(issue) -> Path:
    """Return the resolved file path for an issue, or raise 404."""
    if not issue.file:
        raise HTTPException(404, "Issue has no file")
    p = Path(issue.file.path)
    if not p.is_file():
        raise HTTPException(404, "File not found on disk")
    return p


def _pdf_page_count(path: Path) -> int:
    import fitz
    with fitz.open(str(path)) as doc:
        return len(doc)


def _pdf_render_page(path: Path, page: int) -> bytes:
    import fitz
    with fitz.open(str(path)) as doc:
        if page < 0 or page >= len(doc):
            raise HTTPException(404, "Page out of range")
        pix = doc[page].get_pixmap(dpi=150)
        return pix.tobytes("jpeg")


def _cbz_image_list(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        names = sorted(
            n for n in zf.namelist()
            if Path(n).suffix.lower() in _IMAGE_EXTENSIONS and not n.startswith("__MACOSX")
        )
    return names


def _cbz_page_count(path: Path) -> int:
    return len(_cbz_image_list(path))


def _cbz_render_page(path: Path, page: int) -> tuple[bytes, str]:
    names = _cbz_image_list(path)
    if page < 0 or page >= len(names):
        raise HTTPException(404, "Page out of range")
    with zipfile.ZipFile(path) as zf:
        data = zf.read(names[page])
    ext = Path(names[page]).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp"}
    return data, mime.get(ext.lstrip("."), "image/jpeg")


def _cbr_image_list(path: Path) -> list[str]:
    import rarfile
    with rarfile.RarFile(str(path)) as rf:
        names = sorted(
            n for n in rf.namelist()
            if Path(n).suffix.lower() in _IMAGE_EXTENSIONS and not n.startswith("__MACOSX")
        )
    return names


def _cbr_page_count(path: Path) -> int:
    return len(_cbr_image_list(path))


def _cbr_render_page(path: Path, page: int) -> tuple[bytes, str]:
    import rarfile
    names = _cbr_image_list(path)
    if page < 0 or page >= len(names):
        raise HTTPException(404, "Page out of range")
    with rarfile.RarFile(str(path)) as rf:
        data = rf.read(names[page])
    ext = Path(names[page]).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp"}
    return data, mime.get(ext.lstrip("."), "image/jpeg")


@router.get("/{issue_id}/pages")
async def get_issue_page_count(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Return the number of pages in the issue file."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.issue import Issue

    result = await db.execute(
        select(Issue).options(selectinload(Issue.file)).where(Issue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        raise HTTPException(404, "Issue not found")

    path = _get_issue_file_path(issue)
    fmt = (issue.file.format or path.suffix.lstrip(".")).lower()

    try:
        if fmt == "pdf":
            count = _pdf_page_count(path)
        elif fmt == "cbz":
            count = _cbz_page_count(path)
        elif fmt == "cbr":
            count = _cbr_page_count(path)
        else:
            raise HTTPException(400, f"Unsupported format: {fmt}")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to get page count for issue %d: %s", issue_id, e)
        raise HTTPException(500, f"Failed to read file: {e}")

    return {"pageCount": count, "format": fmt}


@router.get("/{issue_id}/page/{page}")
async def get_issue_page(
    issue_id: int,
    page: int,
    db: AsyncSession = Depends(get_db),
):
    """Render a single page from the issue file as an image."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.issue import Issue

    result = await db.execute(
        select(Issue).options(selectinload(Issue.file)).where(Issue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        raise HTTPException(404, "Issue not found")

    path = _get_issue_file_path(issue)
    fmt = (issue.file.format or path.suffix.lstrip(".")).lower()

    try:
        if fmt == "pdf":
            data = _pdf_render_page(path, page)
            return Response(content=data, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=3600"})
        elif fmt == "cbz":
            data, mime = _cbz_render_page(path, page)
            return Response(content=data, media_type=mime,
                            headers={"Cache-Control": "public, max-age=3600"})
        elif fmt == "cbr":
            data, mime = _cbr_render_page(path, page)
            return Response(content=data, media_type=mime,
                            headers={"Cache-Control": "public, max-age=3600"})
        else:
            raise HTTPException(400, f"Unsupported format: {fmt}")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to render page %d for issue %d: %s", page, issue_id, e)
        raise HTTPException(500, f"Failed to render page: {e}")
