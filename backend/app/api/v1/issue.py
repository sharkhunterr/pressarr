"""Issue management API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.issue import IssueBatchMonitorRequest, IssueResource
from app.services import issue_service

router = APIRouter(prefix="/api/v1/issue", tags=["Issues"])


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
async def update_issue_monitored(
    issue_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Update issue monitoring status."""
    monitored = body.get("monitored")
    if monitored is None:
        raise HTTPException(422, "monitored field is required")
    issue = await issue_service.update_issue_monitored(db, issue_id, monitored)
    if issue is None:
        raise HTTPException(404, "Issue not found")
    return issue


@router.delete("/{issue_id}/file")
async def delete_issue_file(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete the file associated with an issue."""
    deleted = await issue_service.delete_issue_file(db, issue_id)
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
