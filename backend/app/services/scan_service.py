"""Library scan service — discover existing files in root folders and register them."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.issue import Issue
from app.models.issue_file import IssueFile
from app.models.magazine import Magazine
from app.models.quality_profile import QualityProfile
from app.models.root_folder import RootFolder
from app.parser.magazine_parser import (
    ParseResult,
    fuzzy_match_title,
    parse_magazine_filename,
)
from app.services.magazine_service import create_magazine, generate_title_slug

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".epub", ".cbr", ".cbz"}


@dataclass
class ScanProgress:
    """Progress tracking for a library scan."""

    total_files: int = 0
    processed: int = 0
    new_magazines: int = 0
    new_issues: int = 0
    new_files: int = 0
    skipped_existing: int = 0
    skipped_unparseable: int = 0
    errors: int = 0
    current_file: str = ""
    current_root_folder: str = ""
    details: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "totalFiles": self.total_files,
            "processed": self.processed,
            "newMagazines": self.new_magazines,
            "newIssues": self.new_issues,
            "newFiles": self.new_files,
            "skippedExisting": self.skipped_existing,
            "skippedUnparseable": self.skipped_unparseable,
            "errors": self.errors,
            "currentFile": self.current_file,
            "currentRootFolder": self.current_root_folder,
        }


def _count_supported_files(root_folders: list[RootFolder]) -> int:
    """Count all supported files across all root folders for progress reporting."""
    count = 0
    for rf in root_folders:
        root_path = Path(rf.path)
        if not root_path.exists():
            continue
        for f in root_path.rglob("*"):
            if f.suffix.lower() in SUPPORTED_EXTENSIONS and f.is_file():
                count += 1
    return count


def _extract_directory_title(file_path: Path, root_folder_path: str) -> str | None:
    """Extract the first-level subdirectory name as a potential magazine title.

    For /magazines/Science et Vie/2025/file.pdf with root=/magazines,
    returns "Science et Vie".

    For /magazines/file.pdf (file directly in root), returns None.
    """
    try:
        rel = file_path.relative_to(root_folder_path)
        parts = rel.parts
        # parts[0] would be first subdir, parts[-1] is the filename
        if len(parts) > 1:
            return parts[0]
        return None
    except ValueError:
        return None


async def _get_default_quality_profile_id(db: AsyncSession) -> int:
    """Get the first quality profile ID available."""
    result = await db.execute(
        select(QualityProfile.id).limit(1)
    )
    qp_id = result.scalar_one_or_none()
    if qp_id is None:
        raise ValueError("No quality profile found — create one first")
    return qp_id


async def _get_or_create_magazine(
    db: AsyncSession,
    parsed_title: str,
    directory_title: str | None,
    root_folder_id: int,
    default_quality_profile_id: int,
    known_magazines: dict[str, Magazine],
) -> Magazine | None:
    """Match a parsed title to an existing magazine or create a new one."""
    # Build candidate titles (directory title preferred)
    candidates: list[str] = []
    if directory_title:
        candidates.append(directory_title)
    if parsed_title and parsed_title != directory_title:
        candidates.append(parsed_title)

    if not candidates:
        return None

    # 1. Exact slug match (fast path)
    for title in candidates:
        slug = generate_title_slug(title)
        if slug in known_magazines:
            return known_magazines[slug]

    # 2. Fuzzy match against known titles
    known_titles = [m.title for m in known_magazines.values()]
    if known_titles:
        for title in candidates:
            match = fuzzy_match_title(title, known_titles, threshold=80.0)
            if match:
                matched_title, _score = match
                slug = generate_title_slug(matched_title)
                if slug in known_magazines:
                    return known_magazines[slug]

    # 3. Create new magazine
    best_title = candidates[0]
    try:
        magazine = await create_magazine(db, {
            "title": best_title,
            "root_folder_id": root_folder_id,
            "quality_profile_id": default_quality_profile_id,
            "monitored": True,
            "frequency": "monthly",
        })
        await db.flush()
        logger.info("Created new magazine from scan: %s", best_title)
        return magazine
    except ValueError:
        # Duplicate slug — reload from DB
        slug = generate_title_slug(best_title)
        if slug in known_magazines:
            return known_magazines[slug]
        result = await db.execute(
            select(Magazine).where(Magazine.title_slug == slug)
        )
        mag = result.scalars().first()
        return mag


async def _get_or_create_issue(
    db: AsyncSession,
    magazine: Magazine,
    parsed: ParseResult,
) -> tuple[Issue, bool]:
    """Match or create an Issue from parsed data.

    Returns (issue, is_new).
    """
    # 1. Match by number
    if parsed.number is not None:
        result = await db.execute(
            select(Issue).where(
                Issue.magazine_id == magazine.id,
                Issue.number == parsed.number,
            )
        )
        existing = result.scalars().first()
        if existing:
            return existing, False

    # 2. Match by year+month+day
    if parsed.year and parsed.month and parsed.day:
        result = await db.execute(
            select(Issue).where(
                Issue.magazine_id == magazine.id,
                Issue.year == parsed.year,
                Issue.month == parsed.month,
                Issue.day == parsed.day,
            )
        )
        existing = result.scalars().first()
        if existing:
            return existing, False

    # 3. Match by year+month (no day)
    if parsed.year and parsed.month and not parsed.day:
        result = await db.execute(
            select(Issue).where(
                Issue.magazine_id == magazine.id,
                Issue.year == parsed.year,
                Issue.month == parsed.month,
                Issue.day.is_(None),
            )
        )
        existing = result.scalars().first()
        if existing:
            return existing, False

    # 4. Create new issue
    issue = Issue(
        magazine_id=magazine.id,
        number=parsed.number,
        volume=parsed.volume,
        year=parsed.year,
        month=parsed.month,
        day=parsed.day,
        is_special=parsed.is_special,
        status="available",
        monitored=True,
    )
    db.add(issue)
    try:
        await db.flush()
    except Exception:
        # UniqueConstraint violation — reload
        await db.rollback()
        if parsed.number is not None:
            result = await db.execute(
                select(Issue).where(
                    Issue.magazine_id == magazine.id,
                    Issue.number == parsed.number,
                )
            )
            existing = result.scalars().first()
            if existing:
                return existing, False
        # Can't resolve — re-raise
        raise

    return issue, True


async def _register_issue_file(
    db: AsyncSession,
    issue: Issue,
    file_path: Path,
    root_folder_path: str,
    parsed: ParseResult,
) -> bool:
    """Create an IssueFile record for a file already on disk (no move/copy).

    Returns True if a new IssueFile was created.
    """
    # Skip if issue already has a file
    result = await db.execute(
        select(IssueFile).where(IssueFile.issue_id == issue.id)
    )
    if result.scalars().first():
        return False

    relative = str(file_path.relative_to(root_folder_path))
    size = file_path.stat().st_size

    issue_file = IssueFile(
        issue_id=issue.id,
        path=str(file_path),
        relative_path=relative,
        size=size,
        format=parsed.format if parsed.format != "unknown" else file_path.suffix.lstrip(".").lower(),
        quality=parsed.quality,
        original_filename=file_path.name,
        release_group=parsed.release_group,
        language=parsed.language if parsed.language != "unknown" else None,
    )
    db.add(issue_file)

    issue.status = "available"
    await db.flush()
    return True


async def scan_library(
    db: AsyncSession,
    config: Any,
    on_progress: Callable[[ScanProgress], Coroutine[Any, Any, None]] | None = None,
) -> ScanProgress:
    """Scan all root folders for magazine files and register them in the database.

    Files are registered in place (not moved/copied).
    """
    progress = ScanProgress()

    # 1. Load root folders
    result = await db.execute(select(RootFolder))
    root_folders = list(result.scalars().all())
    if not root_folders:
        logger.warning("No root folders configured — nothing to scan")
        return progress

    # 2. Count total files
    progress.total_files = _count_supported_files(root_folders)
    logger.info("Library scan: %d supported files found", progress.total_files)

    # 3. Load existing file paths for fast skip
    existing_result = await db.execute(select(IssueFile.path))
    existing_paths: set[str] = {row[0] for row in existing_result.all()}

    # 4. Build magazine cache (slug -> Magazine)
    mag_result = await db.execute(
        select(Magazine).options(selectinload(Magazine.issues))
    )
    all_magazines = list(mag_result.scalars().all())
    known_magazines: dict[str, Magazine] = {}
    for m in all_magazines:
        known_magazines[generate_title_slug(m.title)] = m

    # 5. Default quality profile
    default_qp_id = await _get_default_quality_profile_id(db)

    # 6. Covers directory
    covers_dir = Path(getattr(config, "config_path", "/config")).parent / "covers"

    # 7. Scan each root folder
    for rf in root_folders:
        progress.current_root_folder = rf.path
        root_path = Path(rf.path)
        if not root_path.exists():
            logger.warning("Root folder does not exist: %s", rf.path)
            continue

        for file_path in sorted(root_path.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            progress.processed += 1
            progress.current_file = file_path.name

            # Skip already registered
            abs_path = str(file_path)
            if abs_path in existing_paths:
                progress.skipped_existing += 1
                if on_progress:
                    await on_progress(progress)
                continue

            try:
                # Parse filename
                parsed = parse_magazine_filename(file_path.name)

                # Directory title hint
                dir_title = _extract_directory_title(file_path, rf.path)

                # Effective title
                effective_title = parsed.title or dir_title
                if not effective_title:
                    progress.skipped_unparseable += 1
                    if on_progress:
                        await on_progress(progress)
                    continue

                # Get or create magazine
                magazine = await _get_or_create_magazine(
                    db, parsed.title, dir_title, rf.id,
                    default_qp_id, known_magazines,
                )
                if not magazine:
                    progress.skipped_unparseable += 1
                    if on_progress:
                        await on_progress(progress)
                    continue

                # Track new magazines
                slug = generate_title_slug(magazine.title)
                if slug not in known_magazines:
                    known_magazines[slug] = magazine
                    progress.new_magazines += 1

                # Get or create issue
                issue, is_new_issue = await _get_or_create_issue(
                    db, magazine, parsed,
                )
                if is_new_issue:
                    progress.new_issues += 1

                # Register file
                registered = await _register_issue_file(
                    db, issue, file_path, rf.path, parsed,
                )
                if registered:
                    progress.new_files += 1
                    existing_paths.add(abs_path)

                    # Extract PDF cover
                    if parsed.format == "pdf" or file_path.suffix.lower() == ".pdf":
                        try:
                            from app.services.import_service import extract_cover

                            cover = await extract_cover(file_path, covers_dir)
                            if cover:
                                issue.cover_path = cover
                                if not magazine.cover_path or magazine.use_latest_issue_cover:
                                    magazine.cover_path = cover
                                await db.flush()
                        except Exception:
                            logger.debug(
                                "Cover extraction failed for %s",
                                file_path,
                                exc_info=True,
                            )
                else:
                    progress.skipped_existing += 1

            except Exception:
                logger.warning("Error scanning %s", file_path, exc_info=True)
                progress.errors += 1

            if on_progress:
                await on_progress(progress)

        # Flush after each root folder
        await db.flush()

    logger.info(
        "Library scan complete: %d files registered, %d magazines created, "
        "%d issues created, %d errors",
        progress.new_files,
        progress.new_magazines,
        progress.new_issues,
        progress.errors,
    )
    return progress
