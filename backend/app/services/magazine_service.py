"""Magazine management service layer."""

import io
import logging
import re
import unicodedata
from datetime import UTC
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.issue import Issue
from app.models.magazine import Magazine
from app.models.magazine_pattern import MagazinePattern
from app.models.magazine_rule import MagazineRule
from app.schemas.magazine import (
    MagazineIdentitySchema,
    MetadataSearchResult,
    SourceInfo,
)

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
    stmt = select(Magazine).options(
        selectinload(Magazine.issues),
        selectinload(Magazine.patterns),
        selectinload(Magazine.rules),
    )

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
        .options(
            selectinload(Magazine.issues),
            selectinload(Magazine.patterns),
            selectinload(Magazine.rules),
        )
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
        # Cascade enrichment fields when caller already has them
        # (allseerr's dispatcher forwards what its search showed).
        language=data.get("language"),
        wikidata_qid=data.get("wikidata_qid"),
        zdb_id=data.get("zdb_id"),
        wikipedia_url=data.get("wikipedia_url"),
        categories=_categories_to_csv(data.get("categories")),
        first_issued=data.get("first_issued"),
        ceased_at=data.get("ceased_at"),
    )

    # When the caller passed an ISSN but no cascade enrichment,
    # back-fill from the cascade ourselves — best-effort, swallows
    # failures so a slow/down provider never blocks magazine
    # creation. Same enrichment shape the manual-add flow would
    # produce when the operator pastes an ISSN directly.
    if magazine.issn and not (
        magazine.wikidata_qid or magazine.zdb_id or magazine.cover_path
    ):
        try:
            from app.metadata.cascade import lookup_issn

            ident = await lookup_issn(magazine.issn, db=db)
            if ident is not None:
                magazine.publisher = magazine.publisher or ident.publisher
                magazine.country = magazine.country or ident.country
                magazine.description = magazine.description or ident.description
                magazine.language = magazine.language or ident.language
                magazine.wikidata_qid = ident.wikidata_qid
                magazine.zdb_id = ident.zdb_id
                magazine.wikipedia_url = ident.wikipedia_url
                magazine.first_issued = ident.first_issued
                magazine.ceased_at = ident.ceased_at
                if ident.categories:
                    magazine.categories = _categories_to_csv(ident.categories)
                magazine.enrichment_status = (
                    "complete"
                    if (ident.publisher and ident.country and ident.language)
                    else "partial"
                )
        except Exception:
            logger.warning(
                "create_magazine: cascade enrichment failed for ISSN %s",
                magazine.issn,
                exc_info=True,
            )

    db.add(magazine)
    await db.flush()
    # Re-fetch with eager-loaded relationships to avoid lazy-load errors
    return await get_magazine(db, magazine.id)  # type: ignore[return-value]


def _categories_to_csv(value) -> str | None:
    """Accepts list[str] (cascade) or str (already CSV from forms)."""
    if value is None:
        return None
    if isinstance(value, list):
        return ",".join(c for c in value if c) or None
    return str(value) or None


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
    # Total issues (exclude forecasts — they're predictions, not real issues)
    total_result = await db.execute(
        select(func.count(Issue.id)).where(
            Issue.magazine_id == magazine_id,
            Issue.is_forecast == False,  # noqa: E712
        )
    )
    issue_count = total_result.scalar() or 0

    # Available issues
    available_result = await db.execute(
        select(func.count(Issue.id)).where(
            Issue.magazine_id == magazine_id,
            Issue.is_forecast == False,  # noqa: E712
            Issue.status == "available",
        )
    )
    available_count = available_result.scalar() or 0

    missing_count = issue_count - available_count
    percent_complete = (available_count / issue_count * 100) if issue_count > 0 else 0.0

    # Next issue date: earliest upcoming forecast
    next_date_result = await db.execute(
        select(Issue.publication_date).where(
            Issue.magazine_id == magazine_id,
            Issue.is_forecast == True,  # noqa: E712
            Issue.status == "upcoming",
            Issue.publication_date.isnot(None),
        ).order_by(Issue.publication_date.asc()).limit(1)
    )
    next_issue_date = next_date_result.scalar()

    return {
        "issue_count": issue_count,
        "available_count": available_count,
        "missing_count": missing_count,
        "percent_complete": round(percent_complete, 1),
        "next_issue_date": next_issue_date,
    }


async def search_metadata(
    query: str,
    config,
    db: AsyncSession | None = None,
    locale: str | None = None,
    status: str | None = None,
    verified_only: bool = False,
) -> list[MetadataSearchResult]:
    """Search every metadata source and deduplicate results.

    Fan-out:
      * ZDB + Wikidata (via ``app.metadata.cascade``) — the ISSN-first
        primary source. Worldwide, free, no auth. Returns identities
        with rich enrichment (cover, country, language, categories).
      * Google Books — fallback cover provider; broad popular catalogue.
      * Internet Archive — covers digitised back-issues that the other
        sources don't index.

    Results merge by ISSN first (canonical for the cascade output),
    then by title slug for entries that aren't ISSN-tagged. Cascade
    enrichment fields (language, wikidata_qid, zdb_id, …) only land
    on the merged entry when the cascade contributed.
    """
    import asyncio

    from app.metadata.cascade import search_cascade
    from app.metadata.google_books import GoogleBooksProvider
    from app.metadata.internet_archive import InternetArchiveProvider

    api_key = getattr(config, "google_books_api_key", None)
    google = GoogleBooksProvider(api_key=api_key)
    archive = InternetArchiveProvider()

    cascade_results, google_results, archive_results = await asyncio.gather(
        search_cascade(query, db=db, locale=locale),
        google.search(query),
        archive.search(query),
        return_exceptions=True,
    )

    # Fetch existing library titles for already_in_library check.
    existing_slugs: set[str] = set()
    if db is not None:
        stmt = select(Magazine.title_slug)
        result = await db.execute(stmt)
        existing_slugs = {row[0] for row in result.all()}

    all_results: list[MetadataSearchResult] = []
    by_slug: dict[str, int] = {}
    by_issn: dict[str, int] = {}

    def _absorb_legacy(r) -> None:
        """Google Books + Internet Archive — legacy MetadataResult."""
        slug = generate_title_slug(r.title)
        source = SourceInfo(provider=r.provider, provider_id=r.provider_id)
        idx = (by_issn.get(r.issn) if r.issn else None) or by_slug.get(slug)
        if idx is not None:
            existing = all_results[idx]
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
                by_issn[r.issn] = idx
            return
        idx = len(all_results)
        by_slug[slug] = idx
        if r.issn:
            by_issn[r.issn] = idx
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

    # Seed first with cascade hits so legacy providers merge INTO the
    # richer identity records (and not the other way round).
    if isinstance(cascade_results, BaseException):
        logger.warning("Cascade error: %s", cascade_results)
    else:
        for ident in cascade_results:
            slug = generate_title_slug(ident.title)
            idx = len(all_results)
            by_slug[slug] = idx
            if ident.issn:
                by_issn[ident.issn] = idx
            sources = [SourceInfo(provider=s, provider_id="") for s in ident.sources]
            all_results.append(
                MetadataSearchResult(
                    provider=(ident.sources[0] if ident.sources else "cascade"),
                    provider_id=(ident.issn or ident.wikidata_qid or slug),
                    title=ident.title,
                    publisher=ident.publisher,
                    country=ident.country,
                    description=ident.description,
                    cover_url=ident.cover_url,
                    issn=ident.issn,
                    frequency=ident.frequency,
                    already_in_library=slug in existing_slugs,
                    sources=sources,
                    language=ident.language,
                    wikidata_qid=ident.wikidata_qid,
                    zdb_id=ident.zdb_id,
                    wikipedia_url=ident.wikipedia_url,
                    categories=ident.categories,
                    first_issued=ident.first_issued,
                    ceased_at=ident.ceased_at,
                )
            )

    for legacy in (google_results, archive_results):
        if isinstance(legacy, BaseException):
            logger.warning("Metadata provider error: %s", legacy)
            continue
        for r in legacy:
            _absorb_legacy(r)

    # Relevance sort: same shape as ``cascade._rank`` so legacy
    # provider hits (Google Books / Internet Archive) interleave
    # cleanly with cascade entries instead of overriding the
    # ISSN-first ordering the cascade already established.
    #
    # Title-match tier first (exact / prefix / substring / other),
    # then "is this a real requestable magazine" signal tier
    # (ISSN + enrichment > ISSN alone > Wikidata-only > catalogue
    # noise) — exact wording mirrors cascade.signal_tier so the
    # explanation stays in one place.
    query_lower = query.lower().strip()

    def _signal_tier(item: MetadataSearchResult) -> int:
        has_issn = bool(item.issn)
        has_wd = bool(item.wikidata_qid)
        has_country = bool(item.country)
        if has_issn and (has_wd or has_country):
            return 0
        if has_issn:
            return 1
        if has_wd:
            return 2
        return 3

    def _ongoing_tier(item: MetadataSearchResult) -> int:
        # Same shape as cascade.ongoing_tier so the search ordering
        # surfaces still-publishing magazines first.
        if item.ceased_at:
            return 2
        if item.first_issued or item.issn or item.wikidata_qid:
            return 0
        return 1

    def _relevance(item: MetadataSearchResult) -> tuple[int, int, int, str]:
        title_lower = item.title.lower().strip()
        if title_lower == query_lower:
            title_tier = 0
        elif title_lower.startswith(query_lower):
            title_tier = 1
        elif query_lower in title_lower:
            title_tier = 2
        else:
            title_tier = 3
        return (
            title_tier,
            _ongoing_tier(item),
            _signal_tier(item),
            title_lower,
        )

    all_results.sort(key=_relevance)

    # Optional status filter (defaults to no filter = return all).
    if status == "ongoing":
        all_results = [r for r in all_results if not r.ceased_at]
    elif status == "ceased":
        all_results = [r for r in all_results if r.ceased_at]

    # "Verified" filter — keep only entries with a Wikidata QID OR
    # an ISSN that the cascade enriched cross-providers (multi-source
    # ``sources`` list). Hides BnF-only / ZDB-only catalogue
    # records that aren't recognised by any worldwide authority,
    # which is what an operator typically wants when noise like
    # "L'Equipe Feder (Montpellier)" or "Le Monde de (Morlaix)"
    # shows up alongside the canonical title they're looking for.
    if verified_only:
        all_results = [
            r
            for r in all_results
            if r.wikidata_qid or (len(r.sources) >= 2)
        ]

    return all_results


async def lookup_magazine_by_issn(
    issn: str,
    db: AsyncSession | None = None,
    locale: str | None = None,
) -> MagazineIdentitySchema | None:
    """Authoritative ISSN → ``MagazineIdentity``.

    Used by the manual-add flow (operator pastes an ISSN) and by
    allseerr's dispatcher to verify the record before promoting a
    cascade hit to a monitored Magazine.
    """
    from app.metadata.cascade import lookup_issn

    ident = await lookup_issn(issn, db=db, locale=locale)
    if ident is None:
        return None
    return MagazineIdentitySchema(
        title=ident.title,
        issn=ident.issn,
        publisher=ident.publisher,
        country=ident.country,
        language=ident.language,
        frequency=ident.frequency,
        cover_url=ident.cover_url,
        description=ident.description,
        first_issued=ident.first_issued,
        ceased_at=ident.ceased_at,
        wikidata_qid=ident.wikidata_qid,
        zdb_id=ident.zdb_id,
        wikipedia_url=ident.wikipedia_url,
        categories=ident.categories,
        sources=ident.sources,
        related_publications=ident.related_publications,
    )


async def refresh_metadata(db: AsyncSession, magazine_id: int) -> str | None:
    """Refresh metadata for a magazine via its configured provider."""
    magazine = await get_magazine(db, magazine_id)
    if magazine is None:
        return f"Magazine {magazine_id} not found"

    if not magazine.metadata_provider or not magazine.metadata_provider_id:
        return "No metadata provider configured"

    from datetime import datetime
    magazine.last_metadata_refresh = datetime.now(UTC)
    await db.flush()

    return f"Metadata refreshed for '{magazine.title}'"


async def refresh_magazine_full(db: AsyncSession, magazine_id: int) -> dict:
    """Full refresh: metadata + disk scan + auto-detect numbers/dates + mark missing."""
    from app.models.root_folder import RootFolder
    from app.parser.magazine_parser import parse_magazine_filename
    from app.services.issue_service import scan_magazine_folder

    stats: dict = {
        "metadata": None,
        "scanned": 0,
        "created": 0,
        "detected": 0,
        "missing_cleared": 0,
        "reassigned": 0,
    }

    # Load magazine with root_folder and issues+files
    stmt = (
        select(Magazine)
        .where(Magazine.id == magazine_id)
        .options(
            selectinload(Magazine.issues).selectinload(Issue.file),
            selectinload(Magazine.patterns),
            selectinload(Magazine.rules),
        )
    )
    result = await db.execute(stmt)
    magazine = result.scalar_one_or_none()
    if magazine is None:
        return stats

    root_folder = await db.get(RootFolder, magazine.root_folder_id)
    if root_folder is None:
        return stats

    # 1. Refresh metadata
    stats["metadata"] = await refresh_metadata(db, magazine_id)

    # 1.5. Detect file/issue mismatches (e.g. file renamed to a different date)
    for issue in magazine.issues:
        if not issue.file:
            continue
        parsed = parse_magazine_filename(Path(issue.file.path).name)

        # Check if dates match — if they do, the file belongs here regardless
        # of number differences (number in filename can be a "000" placeholder)
        dates_match = (
            parsed.year is not None
            and parsed.year == issue.year
            and parsed.month is not None
            and parsed.month == issue.month
            and (parsed.day is None or issue.day is None or parsed.day == issue.day)
        )
        if dates_match:
            continue

        mismatched = False
        # Check by number (ignore 0 — placeholder from naming templates)
        if (
            parsed.number is not None
            and parsed.number > 0
            and issue.number is not None
            and issue.number > 0
        ):
            if parsed.number != issue.number:
                mismatched = True
        # Check by full date (daily papers like Le Monde)
        elif parsed.day is not None and issue.day is not None:
            if (
                parsed.year != issue.year
                or parsed.month != issue.month
                or parsed.day != issue.day
            ):
                mismatched = True
        # Check by year+month (monthly magazines)
        elif parsed.month is not None and issue.month is not None:
            if parsed.year != issue.year or parsed.month != issue.month:
                mismatched = True

        if mismatched:
            await db.delete(issue.file)
            issue.status = "wanted" if issue.monitored else "missing"
            stats["reassigned"] += 1

    if stats["reassigned"]:
        await db.flush()

    # 2. Scan disk for new files
    scan_stats = await scan_magazine_folder(db, magazine, root_folder.path)
    stats["scanned"] = scan_stats["matched"]
    stats["created"] = scan_stats.get("created", 0)

    # Re-load issues after scan to include newly created ones
    await db.refresh(magazine, attribute_names=["issues"])
    for issue in magazine.issues:
        if issue.file is None:
            await db.refresh(issue, attribute_names=["file"])

    # 3. Auto-detect numbers/dates from filenames
    for issue in magazine.issues:
        if not issue.file:
            continue
        updated = False
        parsed = parse_magazine_filename(issue.file.original_filename)
        if parsed.number is not None and issue.number is None:
            issue.number = parsed.number
            updated = True
        if parsed.year is not None and issue.year is None:
            issue.year = parsed.year
            updated = True
        if parsed.month is not None and issue.month is None:
            issue.month = parsed.month
            updated = True
        if parsed.day is not None and issue.day is None:
            issue.day = parsed.day
            updated = True
        if updated:
            stats["detected"] += 1

    # 4. Mark missing files
    for issue in magazine.issues:
        if issue.file and not Path(issue.file.path).exists():
            await db.delete(issue.file)
            issue.status = "wanted" if issue.monitored else "missing"
            stats["missing_cleared"] += 1

    await db.flush()
    return stats


# ---------------------------------------------------------------------------
# Pattern management
# ---------------------------------------------------------------------------


async def add_magazine_pattern(
    db: AsyncSession, magazine_id: int, data: dict
) -> MagazinePattern:
    pattern = MagazinePattern(
        magazine_id=magazine_id,
        pattern=data["pattern"],
        source=data.get("source"),
        uploader=data.get("uploader"),
    )
    db.add(pattern)
    await db.flush()
    return pattern


async def get_magazine_pattern(db: AsyncSession, pattern_id: int) -> MagazinePattern | None:
    result = await db.execute(
        select(MagazinePattern).where(MagazinePattern.id == pattern_id)
    )
    return result.scalar_one_or_none()


async def update_magazine_pattern(
    db: AsyncSession, pattern_id: int, data: dict
) -> MagazinePattern | None:
    result = await db.execute(
        select(MagazinePattern).where(MagazinePattern.id == pattern_id)
    )
    pattern = result.scalar_one_or_none()
    if pattern is None:
        return None
    for key in ("pattern", "source", "uploader"):
        if key in data and data[key] is not None:
            setattr(pattern, key, data[key])
    await db.flush()
    return pattern


async def delete_magazine_pattern(db: AsyncSession, pattern_id: int) -> bool:
    result = await db.execute(
        select(MagazinePattern).where(MagazinePattern.id == pattern_id)
    )
    pattern = result.scalar_one_or_none()
    if pattern is None:
        return False
    await db.delete(pattern)
    await db.flush()
    return True


async def learn_magazine_pattern_from_grab(
    db: AsyncSession, magazine_id: int, torrent_title: str, indexer_name: str
) -> MagazinePattern:
    """Learn a pattern when a magazine torrent is grabbed.

    If an identical pattern exists, update last_seen_at instead of duplicating.
    """
    from datetime import datetime

    existing = await db.execute(
        select(MagazinePattern).where(
            MagazinePattern.magazine_id == magazine_id,
            MagazinePattern.pattern == torrent_title,
        )
    )
    existing_pattern = existing.scalar_one_or_none()
    if existing_pattern:
        existing_pattern.last_seen_at = datetime.now(UTC)
        await db.flush()
        return existing_pattern

    return await add_magazine_pattern(
        db,
        magazine_id,
        {"pattern": torrent_title, "source": indexer_name},
    )


# ---------------------------------------------------------------------------
# Rule management
# ---------------------------------------------------------------------------


async def add_magazine_rule(
    db: AsyncSession, magazine_id: int, data: dict
) -> MagazineRule:
    rule = MagazineRule(
        magazine_id=magazine_id,
        rule_type=data["rule_type"],
        pattern=data["pattern"],
    )
    db.add(rule)
    await db.flush()
    return rule


async def update_magazine_rule(
    db: AsyncSession, rule_id: int, data: dict
) -> MagazineRule | None:
    result = await db.execute(
        select(MagazineRule).where(MagazineRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        return None
    if "rule_type" in data and data["rule_type"] is not None:
        rule.rule_type = data["rule_type"]
    if "pattern" in data and data["pattern"] is not None:
        rule.pattern = data["pattern"]
    await db.flush()
    return rule


async def delete_magazine_rule(db: AsyncSession, rule_id: int) -> bool:
    result = await db.execute(
        select(MagazineRule).where(MagazineRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        return False
    await db.delete(rule)
    await db.flush()
    return True


def apply_magazine_rules(
    rss_title: str, rules: list[MagazineRule]
) -> tuple[bool, str | None]:
    """Apply include/exclude rules to an RSS item title.

    Returns (excluded, reason).
    - If any exclude rule matches -> excluded.
    - If include rules exist, must match at least one, otherwise excluded.
    """
    include_rules = [r for r in rules if r.rule_type == "include"]
    exclude_rules = [r for r in rules if r.rule_type == "exclude"]

    for rule in exclude_rules:
        if re.search(rule.pattern, rss_title, re.IGNORECASE):
            return True, f"Excluded by rule: {rule.pattern}"

    if include_rules:
        for rule in include_rules:
            if re.search(rule.pattern, rss_title, re.IGNORECASE):
                return False, None
        return True, "No include rule matched"

    return False, None
