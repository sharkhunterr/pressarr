"""Issue management service: listing, monitoring, file ops, folder scanning."""

import logging
from pathlib import Path

from sqlalchemy import select
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


async def update_issue(
    db: AsyncSession, issue_id: int, data: dict
) -> Issue | None:
    """Update issue fields (and optionally its file's fields)."""
    issue = await get_issue(db, issue_id)
    if not issue:
        return None

    # Issue-level fields
    issue_fields = {"number", "volume", "title", "year", "month", "day", "monitored", "is_special"}
    for field in issue_fields:
        if field in data and data[field] is not None:
            setattr(issue, field, data[field])

    # Explicit status change (with monitored sync)
    if "status" in data and data["status"] is not None:
        allowed = {"wanted", "missing", "available", "snatched"}
        new_status = data["status"]
        if new_status in allowed:
            issue.status = new_status
            issue.monitored = new_status != "missing"
    elif "monitored" in data and data["monitored"] is not None and issue.status in ("wanted", "missing"):
        # Sync status when only monitored changes
        issue.status = "wanted" if data["monitored"] else "missing"

    # File-level fields
    if issue.file:
        file_fields = {"quality", "format", "release_group", "language"}
        for field in file_fields:
            if field in data and data[field] is not None:
                setattr(issue.file, field, data[field])

        # Rename file on disk if original_filename changed
        new_filename = data.get("original_filename")
        if new_filename and new_filename != Path(issue.file.path).name:
            _rename_issue_file(issue.file, new_filename)

    await db.flush()
    return issue


async def reassign_issue_file(
    db: AsyncSession, source_issue_id: int, target_issue_id: int
) -> tuple[Issue, Issue]:
    """Move a file from one issue to another. Returns (source, target)."""
    source = await get_issue(db, source_issue_id)
    if not source or not source.file:
        raise ValueError("Source issue has no file")

    target = await get_issue(db, target_issue_id)
    if not target:
        raise ValueError("Target issue not found")
    if target.file:
        raise ValueError("Target issue already has a file")

    # Move the file record
    source.file.issue_id = target_issue_id

    # Update source status
    source.status = "wanted" if source.monitored else "missing"

    # Update target status
    target.status = "available"
    if target.is_forecast:
        target.is_forecast = False

    await db.flush()

    # Re-fetch to get updated relationships
    source = await get_issue(db, source_issue_id)
    target = await get_issue(db, target_issue_id)
    return source, target


SUPPORTED_EXTENSIONS = {".pdf", ".epub", ".cbr", ".cbz"}


def _rename_issue_file(issue_file: "IssueFile", new_filename: str) -> None:
    """Rename a physical file on disk and update IssueFile fields."""
    # Validate filename
    if "/" in new_filename or "\\" in new_filename or ".." in new_filename:
        raise ValueError("Invalid filename")

    ext = Path(new_filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported extension: {ext}")

    old_path = Path(issue_file.path)
    if not old_path.exists():
        raise ValueError("Source file not found on disk")

    new_path = old_path.parent / new_filename
    if new_path.exists() and new_path != old_path:
        raise ValueError("A file with that name already exists")

    old_path.rename(new_path)

    # Update DB fields
    old_relative = Path(issue_file.relative_path)
    issue_file.path = str(new_path)
    issue_file.relative_path = str(old_relative.parent / new_filename)


async def delete_issue_file(
    db: AsyncSession, issue_id: int, unmonitor: bool = False
) -> bool:
    issue = await get_issue(db, issue_id)
    if not issue or not issue.file:
        return False

    file_path = Path(issue.file.path)
    if file_path.exists():
        file_path.unlink()

    await db.delete(issue.file)

    if unmonitor:
        issue.monitored = False
        issue.status = "missing"
    else:
        issue.status = "wanted" if issue.monitored else "missing"

    await db.flush()
    return True


async def delete_issue(db: AsyncSession, issue_id: int) -> bool:
    """Delete an issue and its file entirely."""
    issue = await get_issue(db, issue_id)
    if not issue:
        return False

    # Remove physical file if present
    if issue.file:
        file_path = Path(issue.file.path)
        if file_path.exists():
            file_path.unlink()

    await db.delete(issue)
    await db.flush()
    return True


async def refresh_issue_metadata(db: AsyncSession, issue_id: int) -> str | None:
    """Refresh metadata for a single issue via its magazine's metadata provider."""
    issue = await get_issue(db, issue_id)
    if issue is None:
        return f"Issue {issue_id} not found"

    magazine = await db.get(Magazine, issue.magazine_id)
    if magazine is None:
        return f"Magazine for issue {issue_id} not found"

    if not magazine.metadata_provider or not magazine.metadata_provider_id:
        return "No metadata provider configured for this magazine"

    from app.metadata.base import IssueMetadata
    from app.metadata.google_books import GoogleBooksProvider
    from app.metadata.internet_archive import InternetArchiveProvider

    provider_issues: list[IssueMetadata] = []
    try:
        if magazine.metadata_provider == "google_books":
            from app.dependencies import get_config
            config = get_config()
            api_key = getattr(config, "google_books_api_key", None)
            gp = GoogleBooksProvider(api_key=api_key)
            provider_issues = await gp.get_issues(magazine.metadata_provider_id)
        elif magazine.metadata_provider == "internet_archive":
            ia = InternetArchiveProvider()
            provider_issues = await ia.get_issues(magazine.metadata_provider_id)
    except Exception:
        logger.warning("Failed to fetch issue metadata for issue %d", issue_id, exc_info=True)
        return f"Failed to fetch metadata for issue {issue_id}"

    # Try to match the fetched issue data by number
    matched: IssueMetadata | None = None
    for pi in provider_issues:
        if pi.number == issue.number:
            matched = pi
            break

    if matched:
        if matched.title and not issue.title:
            issue.title = matched.title
        if matched.publication_date and not issue.publication_date:
            from datetime import date as date_type
            try:
                d = date_type.fromisoformat(matched.publication_date)
                issue.publication_date = d
                if not issue.year:
                    issue.year = d.year
                if not issue.month:
                    issue.month = d.month
            except ValueError:
                pass
        await db.flush()
        return f"Metadata refreshed for issue #{issue.number}"

    return f"No matching metadata found for issue #{issue.number}"


async def scan_magazine_folder(
    db: AsyncSession,
    magazine: Magazine,
    root_path: str,
) -> dict:
    """Scan magazine folder for existing files.
    Returns stats: {matched, unmatched, errors}.
    """
    from app.parser.magazine_parser import parse_magazine_filename

    stats = {"matched": 0, "unmatched": 0, "created": 0, "errors": 0}
    magazine_dir = Path(root_path) / magazine.title

    if not magazine_dir.exists():
        return stats

    supported = {".pdf", ".epub", ".cbr", ".cbz"}

    for file_path in magazine_dir.rglob("*"):
        if file_path.suffix.lower() not in supported:
            continue

        try:
            parsed = parse_magazine_filename(file_path.name)

            # Try to match by number first, then by date
            # Skip number=0 (placeholder from naming templates like "000")
            issue = None
            if parsed.number is not None and parsed.number > 0:
                result = await db.execute(
                    select(Issue).where(
                        Issue.magazine_id == magazine.id,
                        Issue.number == parsed.number,
                    )
                )
                issue = result.scalars().first()

            # Fallback: match by date (daily/monthly magazines)
            if not issue and parsed.year is not None and parsed.month is not None:
                conditions = [
                    Issue.magazine_id == magazine.id,
                    Issue.year == parsed.year,
                    Issue.month == parsed.month,
                ]
                if parsed.day is not None:
                    conditions.append(Issue.day == parsed.day)
                result = await db.execute(select(Issue).where(*conditions))
                issue = result.scalars().first()

            if not issue:
                # Create a new issue if we have enough date info
                if parsed.year is not None and parsed.month is not None:
                    from datetime import date as date_type

                    try:
                        pub_date = date_type(
                            parsed.year,
                            parsed.month,
                            parsed.day or 1,
                        )
                    except ValueError:
                        stats["unmatched"] += 1
                        continue

                    issue = Issue(
                        magazine_id=magazine.id,
                        number=parsed.number if parsed.number else None,
                        year=parsed.year,
                        month=parsed.month,
                        day=parsed.day,
                        publication_date=pub_date,
                        status="available",
                        monitored=True,
                        is_special=parsed.is_special,
                    )
                    db.add(issue)
                    await db.flush()
                    stats["created"] += 1
                else:
                    stats["unmatched"] += 1
                    continue

            # Check if issue already has a file
            existing = await db.execute(
                select(IssueFile).where(IssueFile.issue_id == issue.id)
            )
            if existing.scalars().first():
                continue

            # Check if file path is already tracked by another issue
            path_existing = await db.execute(
                select(IssueFile).where(IssueFile.path == str(file_path))
            )
            if path_existing.scalars().first():
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
            if issue.is_forecast:
                issue.is_forecast = False
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

        new_name = apply_template(
            naming_template,
            magazine_title=magazine.title,
            number=issue.number,
            volume=issue.volume,
            year=issue.year,
            month=issue.month,
            day=issue.day,
            quality=issue.file.quality,
            file_format=issue.file.format,
            group=issue.file.release_group,
            language=issue.file.language or "unknown",
            is_special=issue.is_special,
        )

        new_path = Path(root_path) / new_name
        rename_info = {"old_path": str(old_path), "new_path": str(new_path)}

        if preview_only:
            results.append(rename_info)
        elif str(old_path) != str(new_path) and old_path.exists():
            import shutil
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_path), str(new_path))
            issue.file.path = str(new_path)
            issue.file.relative_path = str(new_path.relative_to(root_path))
            issue.file.original_filename = new_path.name
            await db.flush()
            results.append(rename_info)

    return results
