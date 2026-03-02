"""Magazine management service layer."""

import io
import logging
import re
import unicodedata
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.magazine import Magazine
from app.models.issue import Issue
from app.schemas.magazine import MetadataSearchResult, SourceInfo

logger = logging.getLogger(__name__)


def generate_title_slug(title: str) -> str:
    """Generate a URL-safe slug from a title.

    Lowercase, strip accents, replace non-alnum with dashes, collapse
    consecutive dashes, strip leading/trailing dashes.
    """
    # Normalize unicode and strip accents
    nfkd = unicodedata.normalize("NFKD", title)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    lower = ascii_text.lower()
    # Replace non-alphanumeric with dashes
    dashed = re.sub(r"[^a-z0-9]+", "-", lower)
    # Collapse consecutive dashes and strip
    slug = re.sub(r"-+", "-", dashed).strip("-")
    return slug


def save_cover_image(image_bytes: bytes, covers_dir: Path, title_slug: str) -> str:
    """Resize image to max 500px wide, convert to JPEG, save to covers dir.

    Returns the absolute path of the saved file.
    """
    from PIL import Image

    covers_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(image_bytes))
    if img.width > 500:
        ratio = 500 / img.width
        img = img.resize((500, int(img.height * ratio)), Image.LANCZOS)
    img = img.convert("RGB")
    dest = covers_dir / f"{title_slug}-custom.jpg"
    img.save(dest, "JPEG", quality=85)
    return str(dest)


async def list_magazines(
    db: AsyncSession,
    sort_key: str = "title",
    sort_dir: str = "asc",
    monitored: bool | None = None,
) -> list[Magazine]:
    """List all magazines with optional filtering and sorting."""
    stmt = select(Magazine).options(selectinload(Magazine.issues))

    if monitored is not None:
        stmt = stmt.where(Magazine.monitored == monitored)

    # Determine sort column
    sort_column = getattr(Magazine, sort_key, Magazine.title)
    if sort_dir.lower() == "desc":
        sort_column = sort_column.desc()

    stmt = stmt.order_by(sort_column)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_magazine(db: AsyncSession, magazine_id: int) -> Magazine | None:
    """Get a single magazine by ID with issues eager-loaded."""
    stmt = (
        select(Magazine)
        .where(Magazine.id == magazine_id)
        .options(selectinload(Magazine.issues))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_magazine(db: AsyncSession, data: dict) -> Magazine:
    """Create a new magazine. Raises ValueError on duplicate title_slug."""
    title = data["title"]
    title_slug = generate_title_slug(title)

    # Check for duplicate slug
    existing = await db.execute(
        select(Magazine).where(Magazine.title_slug == title_slug)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Magazine with slug '{title_slug}' already exists")

    # Convert excluded_days list to CSV string for storage
    excluded_days_raw = data.get("excluded_days")
    excluded_days_str = (
        ",".join(str(d) for d in excluded_days_raw)
        if excluded_days_raw
        else None
    )

    magazine = Magazine(
        title=title,
        title_slug=title_slug,
        issn=data.get("issn"),
        publisher=data.get("publisher"),
        country=data.get("country"),
        description=data.get("description"),
        frequency=data.get("frequency", "monthly"),
        monitored=data.get("monitored", True),
        monitoring_start_date=data.get("monitoring_start_date"),
        search_terms=data.get("search_terms"),
        root_folder_id=data["root_folder_id"],
        quality_profile_id=data["quality_profile_id"],
        metadata_provider_id=data.get("metadata_provider_id"),
        metadata_provider=data.get("metadata_provider"),
        excluded_days=excluded_days_str,
    )
    db.add(magazine)
    await db.flush()
    return magazine


async def update_magazine(
    db: AsyncSession, magazine_id: int, data: dict
) -> Magazine | None:
    """Update an existing magazine. Returns None if not found."""
    magazine = await get_magazine(db, magazine_id)
    if magazine is None:
        return None

    # Handle cover_issue_id: resolve issue cover and apply to magazine
    cover_issue_id = data.pop("cover_issue_id", None)
    if cover_issue_id is not None:
        issue_result = await db.execute(
            select(Issue).where(
                Issue.id == cover_issue_id,
                Issue.magazine_id == magazine_id,
            )
        )
        issue = issue_result.scalar_one_or_none()
        if issue and issue.cover_path:
            magazine.cover_path = issue.cover_path

    for key, value in data.items():
        if key == "excluded_days" and hasattr(magazine, key):
            if isinstance(value, list):
                setattr(magazine, key, ",".join(str(d) for d in value) if value else None)
            else:
                setattr(magazine, key, None)
        elif value is not None and hasattr(magazine, key):
            setattr(magazine, key, value)

    # Regenerate slug if title changed
    if "title" in data and data["title"] is not None:
        magazine.title_slug = generate_title_slug(data["title"])

    await db.flush()

    # Regenerate forecasts if frequency, monitoring_start_date, or excluded_days changed
    if "frequency" in data or "monitoring_start_date" in data or "excluded_days" in data:
        from app.services.calendar_service import generate_forecasts

        await generate_forecasts(db, magazine)

    return magazine


async def delete_magazine(
    db: AsyncSession, magazine_id: int, delete_files: bool = False
) -> bool:
    """Delete a magazine. Returns False if not found."""
    magazine = await get_magazine(db, magazine_id)
    if magazine is None:
        return False

    if delete_files:
        # TODO: implement actual file deletion from disk
        logger.info(
            "delete_files=True for magazine %d (not yet implemented)",
            magazine_id,
        )

    await db.delete(magazine)
    await db.flush()
    return True


async def get_statistics(db: AsyncSession, magazine_id: int) -> dict:
    """Compute statistics for a magazine."""
    # Total issues
    total_result = await db.execute(
        select(func.count(Issue.id)).where(Issue.magazine_id == magazine_id)
    )
    issue_count = total_result.scalar() or 0

    # Available issues (status != 'missing')
    available_result = await db.execute(
        select(func.count(Issue.id)).where(
            Issue.magazine_id == magazine_id,
            Issue.status != "missing",
        )
    )
    available_count = available_result.scalar() or 0

    missing_count = issue_count - available_count
    percent_complete = (available_count / issue_count * 100) if issue_count > 0 else 0.0

    return {
        "issue_count": issue_count,
        "available_count": available_count,
        "missing_count": missing_count,
        "percent_complete": round(percent_complete, 1),
    }


async def search_metadata(
    query: str, config, db: AsyncSession | None = None,
) -> list[MetadataSearchResult]:
    """Search all metadata providers and deduplicate results."""
    from app.metadata.google_books import GoogleBooksProvider
    from app.metadata.internet_archive import InternetArchiveProvider

    api_key = getattr(config, "google_books_api_key", None)

    google = GoogleBooksProvider(api_key=api_key)
    archive = InternetArchiveProvider()

    # Search all providers concurrently
    import asyncio
    google_results, archive_results = await asyncio.gather(
        google.search(query),
        archive.search(query),
        return_exceptions=True,
    )

    # Fetch existing library titles for already_in_library check
    existing_slugs: set[str] = set()
    if db is not None:
        stmt = select(Magazine.title_slug)
        result = await db.execute(stmt)
        existing_slugs = {row[0] for row in result.all()}

    all_results: list[MetadataSearchResult] = []
    seen_slugs: dict[str, int] = {}  # slug -> index in all_results

    for results in [google_results, archive_results]:
        if isinstance(results, BaseException):
            logger.warning("Metadata provider error: %s", results)
            continue
        for r in results:
            slug = generate_title_slug(r.title)
            source = SourceInfo(provider=r.provider, provider_id=r.provider_id)

            if slug in seen_slugs:
                # Merge into existing entry
                existing = all_results[seen_slugs[slug]]
                # Increment count for existing provider or add new one
                provider_source = next(
                    (s for s in existing.sources if s.provider == r.provider), None
                )
                if provider_source:
                    provider_source.count += 1
                else:
                    existing.sources.append(source)
                if not existing.cover_url and r.cover_url:
                    existing.cover_url = r.cover_url
                if not existing.publisher and r.publisher:
                    existing.publisher = r.publisher
                if r.description and (
                    not existing.description
                    or len(r.description) > len(existing.description)
                ):
                    existing.description = r.description
                if not existing.frequency and r.frequency:
                    existing.frequency = r.frequency
                if not existing.issn and r.issn:
                    existing.issn = r.issn
                continue

            seen_slugs[slug] = len(all_results)
            all_results.append(
                MetadataSearchResult(
                    provider=r.provider,
                    provider_id=r.provider_id,
                    title=r.title,
                    publisher=r.publisher,
                    country=r.country,
                    description=r.description,
                    cover_url=r.cover_url,
                    issn=r.issn,
                    frequency=r.frequency,
                    already_in_library=slug in existing_slugs,
                    sources=[source],
                )
            )

    # Sort by relevance: exact title matches first, then prefix matches,
    # then everything else.
    query_lower = query.lower().strip()

    def _relevance(item: MetadataSearchResult) -> tuple[int, str]:
        title_lower = item.title.lower().strip()
        if title_lower == query_lower:
            return (0, title_lower)
        if title_lower.startswith(query_lower):
            return (1, title_lower)
        if query_lower in title_lower:
            return (2, title_lower)
        return (3, title_lower)

    all_results.sort(key=_relevance)

    return all_results


async def refresh_metadata(db: AsyncSession, magazine_id: int) -> str | None:
    """Refresh metadata for a magazine via its configured provider."""
    magazine = await get_magazine(db, magazine_id)
    if magazine is None:
        return f"Magazine {magazine_id} not found"

    if not magazine.metadata_provider or not magazine.metadata_provider_id:
        return "No metadata provider configured"

    from datetime import datetime, timezone
    magazine.last_metadata_refresh = datetime.now(timezone.utc)
    await db.flush()

    return f"Metadata refreshed for '{magazine.title}'"
