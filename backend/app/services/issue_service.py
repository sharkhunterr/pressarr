"""Issue management service: listing, monitoring, file ops, folder scanning."""

import logging
from pathlib import Path

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.issue import Issue
from app.models.issue_file import IssueFile
from app.models.magazine import Magazine

logger = logging.getLogger(__name__)


async def list_issues(
    db: AsyncSession,
    magazine_id: int | None = None,
    status: str | None = None,
) -> list[Issue]:
    query = select(Issue).options(selectinload(Issue.file))
    if magazine_id is not None:
        query = query.where(Issue.magazine_id == magazine_id)
    if status is not None:
        query = query.where(Issue.status == status)
    query = query.order_by(Issue.publication_date.desc().nullslast(), Issue.number.desc().nullslast())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_issue(db: AsyncSession, issue_id: int) -> Issue | None:
    result = await db.execute(
        select(Issue).options(selectinload(Issue.file)).where(Issue.id == issue_id)
    )
    return result.scalars().first()


async def create_issue(db: AsyncSession, **kwargs) -> Issue:
    issue = Issue(**kwargs)
    db.add(issue)
    await db.flush()
    return issue


async def update_issue_monitored(
    db: AsyncSession, issue_id: int, monitored: bool
) -> Issue | None:
    issue = await get_issue(db, issue_id)
    if not issue:
        return None
    issue.monitored = monitored
    if monitored and issue.status == "missing":
        issue.status = "wanted"
    elif not monitored and issue.status == "wanted":
        issue.status = "missing"
    await db.flush()
    return issue


async def batch_monitor(
    db: AsyncSession, issue_ids: list[int], monitored: bool
) -> int:
    count = 0
    for iid in issue_ids:
        result = await update_issue_monitored(db, iid, monitored)
        if result:
            count += 1
    return count


async def delete_issue_file(db: AsyncSession, issue_id: int) -> bool:
    issue = await get_issue(db, issue_id)
    if not issue or not issue.file:
        return False

    file_path = Path(issue.file.path)
    if file_path.exists():
        file_path.unlink()

    await db.delete(issue.file)
    issue.status = "wanted" if issue.monitored else "missing"
    await db.flush()
    return True


async def scan_magazine_folder(
    db: AsyncSession,
    magazine: Magazine,
    root_path: str,
) -> dict:
    """Scan magazine folder for existing files.
    Returns stats: {matched, unmatched, errors}.
    """
    from app.parser.magazine_parser import parse_magazine_filename

    stats = {"matched": 0, "unmatched": 0, "errors": 0}
    magazine_dir = Path(root_path) / magazine.title

    if not magazine_dir.exists():
        return stats

    supported = {".pdf", ".epub", ".cbr", ".cbz"}

    for file_path in magazine_dir.rglob("*"):
        if file_path.suffix.lower() not in supported:
            continue

        try:
            parsed = parse_magazine_filename(file_path.name)

            # Try to match by number
            issue = None
            if parsed.number is not None:
                result = await db.execute(
                    select(Issue).where(
                        Issue.magazine_id == magazine.id,
                        Issue.number == parsed.number,
                    )
                )
                issue = result.scalars().first()

            if not issue:
                stats["unmatched"] += 1
                continue

            # Check if issue already has a file
            existing = await db.execute(
                select(IssueFile).where(IssueFile.issue_id == issue.id)
            )
            if existing.scalars().first():
                continue

            issue_file = IssueFile(
                issue_id=issue.id,
                path=str(file_path),
                relative_path=str(file_path.relative_to(root_path)),
                size=file_path.stat().st_size,
                format=parsed.format,
                quality=parsed.quality,
                original_filename=file_path.name,
                release_group=parsed.release_group,
                language=parsed.language if parsed.language != "unknown" else None,
            )
            db.add(issue_file)
            issue.status = "available"
            await db.flush()
            stats["matched"] += 1

        except Exception:
            logger.warning("Error scanning file %s", file_path, exc_info=True)
            stats["errors"] += 1

    return stats


async def rename_issues(
    db: AsyncSession,
    magazine: Magazine,
    naming_template: str,
    root_path: str,
    preview_only: bool = True,
) -> list[dict]:
    """Rename/move issue files per naming template.
    Returns list of {old_path, new_path} dicts.
    """
    from app.services.import_service import apply_template

    results = []
    issues = await list_issues(db, magazine_id=magazine.id)

    for issue in issues:
        if not issue.file:
            continue

        old_path = Path(issue.file.path)
        if not old_path.exists():
            continue

        new_name = apply_template(
            naming_template,
            magazine_title=magazine.title,
            number=issue.number,
            volume=issue.volume,
            year=issue.year,
            month=issue.month,
            quality=issue.file.quality,
            file_format=issue.file.format,
            group=issue.file.release_group,
            language=issue.file.language or "unknown",
        )

        new_path = Path(root_path) / new_name
        rename_info = {"old_path": str(old_path), "new_path": str(new_path)}
        results.append(rename_info)

        if not preview_only and str(old_path) != str(new_path):
            import shutil
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_path), str(new_path))
            issue.file.path = str(new_path)
            issue.file.relative_path = str(new_path.relative_to(root_path))
            await db.flush()

    return results
