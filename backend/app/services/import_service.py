"""Import pipeline and naming template system."""

import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Default naming template
DEFAULT_TEMPLATE = "{magazine_title}/{magazine_title} - {number} ({year}-{month:02d}).{format}"

# Valid template variables
TEMPLATE_VARIABLES = {
    "magazine_title": "Magazine title",
    "number": "Issue number",
    "volume": "Volume number",
    "year": "Publication year",
    "month": "Publication month (01-12)",
    "quality": "File quality (truepdf, retail, etc.)",
    "format": "File format (pdf, epub, etc.)",
    "group": "Release group name",
    "language": "Language code",
}

# Characters not allowed in filenames
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def validate_template(template: str) -> tuple[bool, str]:
    """Validate a naming template. Returns (is_valid, error_message)."""
    if not template:
        return False, "Template cannot be empty"

    if INVALID_CHARS.search(template.replace("{", "").replace("}", "")):
        return False, "Template contains invalid filesystem characters"

    # Check all variables are recognized
    found_vars = re.findall(r"\{(\w+)(?::[^}]*)?\}", template)
    for var in found_vars:
        if var not in TEMPLATE_VARIABLES:
            return False, f"Unknown template variable: {{{var}}}"

    if not found_vars:
        return False, "Template must contain at least one variable"

    return True, ""


def apply_template(
    template: str,
    magazine_title: str = "",
    number: int | None = None,
    volume: int | None = None,
    year: int | None = None,
    month: int | None = None,
    quality: str = "unknown",
    file_format: str = "pdf",
    group: str | None = None,
    language: str = "unknown",
) -> str:
    """Apply naming template with given values."""
    result = template

    values = {
        "magazine_title": _sanitize_filename(magazine_title) if magazine_title else "Unknown",
        "number": str(number) if number is not None else "000",
        "volume": str(volume) if volume is not None else "",
        "year": str(year) if year is not None else "0000",
        "month": f"{month:02d}" if month is not None else "00",
        "quality": quality,
        "format": file_format.lower().lstrip("."),
        "group": group or "",
        "language": language,
    }

    # Handle format specifiers like {month:02d}
    for var_name, value in values.items():
        # Simple replacement without format spec
        result = result.replace(f"{{{var_name}}}", value)
        # Also handle format specs by replacing them with the pre-formatted value
        result = re.sub(rf"\{{{var_name}:[^}}]*\}}", value, result)

    # Clean up empty segments
    result = re.sub(r" +- +\(\d{4}-00\)", "", result)  # Remove date if no month
    result = re.sub(r"\(\s*\)", "", result)  # Remove empty parens
    result = re.sub(r" {2,}", " ", result)  # Collapse multiple spaces
    result = result.strip()

    return result


def preview_template(template: str) -> str:
    """Generate a preview of the template with sample data."""
    return apply_template(
        template,
        magazine_title="Science et Vie",
        number=1285,
        volume=None,
        year=2025,
        month=3,
        quality="truepdf",
        file_format="pdf",
        group="TeamRelease",
        language="french",
    )


def _sanitize_filename(name: str) -> str:
    """Remove invalid filesystem characters from a filename part."""
    return INVALID_CHARS.sub("", name).strip()


async def extract_cover(pdf_path: str | Path, output_dir: str | Path) -> str | None:
    """Extract cover image from first page of PDF.
    Returns path to cover image or None on failure.
    """
    import asyncio
    from functools import partial

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cover_path = output_dir / f"{pdf_path.stem}.jpg"

    def _extract() -> str | None:
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(pdf_path))
            if len(doc) == 0:
                doc.close()
                return None

            page = doc[0]
            # Render at 2x for quality, then we get a good resolution
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)

            # Resize to max 500px wide
            if pix.width > 500:
                scale = 500 / pix.width
                mat = fitz.Matrix(scale * 2, scale * 2)
                pix = page.get_pixmap(matrix=mat)

            pix.save(str(cover_path))
            doc.close()
            return str(cover_path)
        except Exception:
            logger.warning("Failed to extract cover from %s", pdf_path, exc_info=True)
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract)


async def import_file(
    file_path: Path,
    library_path: Path,
    magazine_title: str,
    naming_template: str,
    number: int | None = None,
    volume: int | None = None,
    year: int | None = None,
    month: int | None = None,
    quality: str = "unknown",
    file_format: str = "pdf",
    group: str | None = None,
    language: str = "unknown",
) -> Path:
    """Move and rename a file into the library using the naming template.
    Returns the new file path.
    """
    new_name = apply_template(
        naming_template,
        magazine_title=magazine_title,
        number=number,
        volume=volume,
        year=year,
        month=month,
        quality=quality,
        file_format=file_format,
        group=group,
        language=language,
    )

    dest = library_path / new_name
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Check disk space
    usage = shutil.disk_usage(dest.parent)
    file_size = file_path.stat().st_size
    if usage.free < file_size * 1.1:  # 10% margin
        raise OSError(f"Insufficient disk space: {usage.free} free, need {file_size}")

    shutil.move(str(file_path), str(dest))
    logger.info("Imported %s → %s", file_path.name, dest)
    return dest


async def process_downloaded_file(
    db,
    file_path: Path,
    config,
    magazine_id: int | None = None,
) -> dict:
    """Full import pipeline: parse → match → rename → move → update DB → cover → notify.

    When magazine_id is provided (e.g. from Manual Research), the fuzzy title
    matching step is skipped and the magazine is loaded directly by ID.

    Returns a dict with keys: success, issue_id, message.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.issue import Issue
    from app.models.issue_file import IssueFile
    from app.models.magazine import Magazine
    from app.models.root_folder import RootFolder
    from app.parser.magazine_parser import parse_magazine_filename, fuzzy_match_title
    from app.services.history_service import create_event
    from app.services.quality_service import should_upgrade

    supported = {".pdf", ".epub", ".cbr", ".cbz"}
    if file_path.suffix.lower() not in supported:
        return {"success": False, "issue_id": None, "message": "Unsupported file format"}

    # 1. Parse filename
    parsed = parse_magazine_filename(file_path.name)

    # 2. Resolve magazine — either by ID (fast path) or fuzzy match
    magazine = None
    if magazine_id:
        mag_result = await db.execute(
            select(Magazine).where(Magazine.id == magazine_id)
        )
        magazine = mag_result.scalars().first()
        if magazine:
            logger.info("Resolved magazine by ID: %s (id=%d)", magazine.title, magazine_id)

    if not magazine:
        # Need a parseable title for fuzzy matching
        if not parsed.title:
            logger.warning("Could not parse title from %s", file_path.name)
            return {"success": False, "issue_id": None, "message": "Unparseable filename"}

        mag_result = await db.execute(select(Magazine))
        magazines = mag_result.scalars().all()
        known_titles = [m.title for m in magazines]

        match = fuzzy_match_title(parsed.title, known_titles, threshold=80.0)
        if not match:
            # Move to unmatched directory
            unmatched_dir = Path(config.download_path) / "unmatched" if hasattr(config, "download_path") else file_path.parent / "unmatched"
            unmatched_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(unmatched_dir / file_path.name))
            await create_event(db, "unmatched", details=f"Unmatched file: {file_path.name}")
            return {"success": False, "issue_id": None, "message": f"No matching magazine for '{parsed.title}'"}

        matched_title, match_score = match
        magazine = next(m for m in magazines if m.title == matched_title)

    # 3. Match issue by number or date
    issue = None
    if parsed.number is not None:
        issue_result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.file))
            .where(Issue.magazine_id == magazine.id, Issue.number == parsed.number)
        )
        issue = issue_result.scalars().first()

    if not issue and parsed.year and parsed.month:
        issue_result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.file))
            .where(
                Issue.magazine_id == magazine.id,
                Issue.year == parsed.year,
                Issue.month == parsed.month,
            )
        )
        issue = issue_result.scalars().first()

    # Save eagerly-loaded file reference before potentially creating a new issue
    # (avoids lazy-load MissingGreenlet errors in background tasks)
    existing_file = None if issue is None else issue.file

    if not issue:
        # Create a new issue for this file
        issue = Issue(
            magazine_id=magazine.id,
            number=parsed.number,
            year=parsed.year,
            month=parsed.month,
            is_special=parsed.is_special,
            status="available",
            monitored=True,
        )
        db.add(issue)
        await db.flush()

    # 4. Check quality upgrade
    if existing_file:
        quality_items = []
        if magazine.quality_profile_id:
            from app.models.quality_profile import QualityProfileItem
            qi_result = await db.execute(
                select(QualityProfileItem).where(
                    QualityProfileItem.quality_profile_id == magazine.quality_profile_id
                )
            )
            quality_items = [
                {"quality": qi.quality, "allowed": qi.allowed, "sort_order": qi.sort_order}
                for qi in qi_result.scalars().all()
            ]

        cutoff = "pdf_hq"
        if magazine.quality_profile_id:
            from app.models.quality_profile import QualityProfile
            qp_result = await db.execute(
                select(QualityProfile).where(QualityProfile.id == magazine.quality_profile_id)
            )
            qp = qp_result.scalars().first()
            if qp:
                cutoff = qp.cutoff

        if not should_upgrade(existing_file.quality, parsed.quality, cutoff, quality_items):
            logger.info("Skipping %s — quality %s not an upgrade over %s", file_path.name, parsed.quality, existing_file.quality)
            return {"success": False, "issue_id": issue.id, "message": "Not a quality upgrade"}

        # Remove old file
        old_path = Path(existing_file.path)
        if old_path.exists():
            old_path.unlink()
        await db.delete(existing_file)
        await db.flush()

    # 5. Get library path from root folder
    rf_result = await db.execute(
        select(RootFolder).where(RootFolder.id == magazine.root_folder_id)
    )
    root_folder = rf_result.scalars().first()
    library_path = Path(root_folder.path) if root_folder else Path("/magazines")

    # 6. Apply naming template and move file
    naming_template = getattr(config, "naming_template", DEFAULT_TEMPLATE)

    try:
        dest = await import_file(
            file_path=file_path,
            library_path=library_path,
            magazine_title=magazine.title,
            naming_template=naming_template,
            number=parsed.number,
            volume=parsed.volume,
            year=parsed.year,
            month=parsed.month,
            quality=parsed.quality,
            file_format=parsed.format,
            group=parsed.release_group,
            language=parsed.language,
        )
    except OSError as e:
        await create_event(
            db, "error",
            magazine_id=magazine.id,
            issue_id=issue.id,
            details=f"Import failed: {e}",
        )
        return {"success": False, "issue_id": issue.id, "message": str(e)}

    # 7. Create IssueFile record
    issue_file = IssueFile(
        issue_id=issue.id,
        path=str(dest),
        relative_path=str(dest.relative_to(library_path)),
        size=dest.stat().st_size,
        format=parsed.format,
        quality=parsed.quality,
        original_filename=file_path.name,
        release_group=parsed.release_group,
        language=parsed.language if parsed.language != "unknown" else None,
    )
    db.add(issue_file)

    # 8. Update issue status
    issue.status = "available"
    await db.flush()

    # 9. Extract cover
    covers_dir = Path(getattr(config, "config_path", "/config")).parent / "covers"
    cover = await extract_cover(dest, covers_dir)
    if cover:
        issue.cover_path = cover
        await db.flush()

    # 10. Create history event
    event_type = "upgrade" if existing_file else "import"
    await create_event(
        db, event_type,
        magazine_id=magazine.id,
        issue_id=issue.id,
        details=f"Imported: {dest.name} ({parsed.quality})",
    )

    # 11. Dispatch notifications
    try:
        from app.notifications.base import NotificationPayload
        from app.services.notification_service import dispatch
        payload = NotificationPayload(
            event_type=event_type,
            magazine_title=magazine.title,
            issue_number=parsed.number,
            quality=parsed.quality,
            cover_url=f"/api/v1/issue/{issue.id}/cover" if cover else None,
        )
        await dispatch(db, event_type, payload)
    except Exception:
        logger.warning("Notification dispatch failed", exc_info=True)

    # 12. Reconcile forecast
    try:
        from app.services.calendar_service import reconcile_forecast
        await reconcile_forecast(db, issue)
    except Exception:
        logger.debug("Forecast reconciliation skipped", exc_info=True)

    return {"success": True, "issue_id": issue.id, "message": f"Imported to {dest}"}


async def import_file_for_issue(
    db,
    file_path: Path,
    issue_id: int,
    config,
) -> dict:
    """Import a downloaded file directly for a known issue (skips filename parsing).

    Used by IA/AA downloads where the issue is already known.
    Returns a dict with keys: success, issue_id, message.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.issue import Issue
    from app.models.issue_file import IssueFile
    from app.models.magazine import Magazine
    from app.models.root_folder import RootFolder
    from app.services.history_service import create_event

    supported = {".pdf", ".epub", ".cbr", ".cbz"}
    if file_path.suffix.lower() not in supported:
        return {
            "success": False,
            "issue_id": issue_id,
            "message": "Unsupported file format",
        }

    # 1. Load issue with its magazine
    issue_result = await db.execute(
        select(Issue)
        .options(selectinload(Issue.file))
        .where(Issue.id == issue_id)
    )
    issue = issue_result.scalars().first()
    if not issue:
        return {
            "success": False,
            "issue_id": issue_id,
            "message": f"Issue {issue_id} not found",
        }

    mag_result = await db.execute(
        select(Magazine).where(Magazine.id == issue.magazine_id)
    )
    magazine = mag_result.scalars().first()
    if not magazine:
        return {
            "success": False,
            "issue_id": issue_id,
            "message": "Magazine not found",
        }

    # 2. If issue already has a file, replace it
    if issue.file:
        old_path = Path(issue.file.path)
        if old_path.exists():
            old_path.unlink()
        await db.delete(issue.file)
        await db.flush()

    # 3. Get library path
    rf_result = await db.execute(
        select(RootFolder).where(
            RootFolder.id == magazine.root_folder_id
        )
    )
    root_folder = rf_result.scalars().first()
    library_path = (
        Path(root_folder.path) if root_folder else Path("/magazines")
    )

    # 4. Determine file format from extension
    file_format = file_path.suffix.lstrip(".").lower() or "pdf"

    # 5. Apply naming template and move file
    naming_template = getattr(
        config, "naming_template", DEFAULT_TEMPLATE
    )
    try:
        dest = await import_file(
            file_path=file_path,
            library_path=library_path,
            magazine_title=magazine.title,
            naming_template=naming_template,
            number=issue.number,
            year=issue.year,
            month=issue.month,
            quality="unknown",
            file_format=file_format,
        )
    except OSError as e:
        await create_event(
            db, "error",
            magazine_id=magazine.id,
            issue_id=issue.id,
            details=f"Import failed: {e}",
        )
        return {
            "success": False,
            "issue_id": issue.id,
            "message": str(e),
        }

    # 6. Create IssueFile record
    issue_file = IssueFile(
        issue_id=issue.id,
        path=str(dest),
        relative_path=str(dest.relative_to(library_path)),
        size=dest.stat().st_size,
        format=file_format,
        quality="unknown",
        original_filename=file_path.name,
    )
    db.add(issue_file)

    # 7. Update issue status
    issue.status = "available"
    await db.flush()

    # 8. Extract cover
    covers_dir = (
        Path(getattr(config, "config_path", "/config")).parent / "covers"
    )
    cover = await extract_cover(dest, covers_dir)
    if cover:
        issue.cover_path = cover
        await db.flush()

    # 9. Create history event
    await create_event(
        db, "import",
        magazine_id=magazine.id,
        issue_id=issue.id,
        details=f"Imported: {dest.name}",
    )

    # 10. Dispatch notifications
    try:
        from app.notifications.base import NotificationPayload
        from app.services.notification_service import dispatch
        payload = NotificationPayload(
            event_type="import",
            magazine_title=magazine.title,
            issue_number=issue.number,
            quality="unknown",
            cover_url=(
                f"/api/v1/issue/{issue.id}/cover" if cover
                else None
            ),
        )
        await dispatch(db, "import", payload)
    except Exception:
        logger.warning("Notification dispatch failed", exc_info=True)

    # 11. Reconcile forecast
    try:
        from app.services.calendar_service import reconcile_forecast
        await reconcile_forecast(db, issue)
    except Exception:
        logger.debug("Forecast reconciliation skipped", exc_info=True)

    return {
        "success": True,
        "issue_id": issue.id,
        "message": f"Imported to {dest}",
    }
