"""Search and scoring service."""
import logging
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.issue import Issue
from app.models.magazine import Magazine
from app.models.quality_profile import QualityProfile, QualityProfileItem
from app.parser.magazine_parser import parse_magazine_filename, fuzzy_match_title
from app.schemas.search import SearchResultResource
from app.services.history_service import is_blocklisted
from app.services.quality_service import QUALITY_ORDER

logger = logging.getLogger(__name__)

# Build a dict mapping quality name -> index for scoring purposes.
_QUALITY_INDEX: dict[str, int] = {q: i for i, q in enumerate(QUALITY_ORDER)}


async def search_issue(
    db: AsyncSession, issue_id: int, config
) -> list[SearchResultResource]:
    result = await db.execute(
        select(Issue)
        .options(selectinload(Issue.magazine))
        .where(Issue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        return []

    magazine = issue.magazine
    query = _build_query(magazine, issue)

    # Get quality profile items
    profile_items = await _get_quality_items(db, magazine.quality_profile_id)

    # Search via Prowlarr
    from app.indexers.prowlarr import ProwlarrClient
    from app.models.indexer_config import IndexerConfig

    indexer_result = await db.execute(
        select(IndexerConfig).where(IndexerConfig.enabled.is_(True))
    )
    indexers = indexer_result.scalars().all()

    all_results: list[SearchResultResource] = []
    for indexer in indexers:
        try:
            client = ProwlarrClient(
                url=indexer.url,
                api_key=indexer.api_key,
            )
            raw_results = await client.search(query, categories=[7010, 7020])
            for raw in raw_results:
                parsed = parse_magazine_filename(raw.title)
                quality = parsed.quality if parsed.quality != "unknown" else "unknown"
                language = parsed.language if parsed.language != "unknown" else "unknown"

                blocked = await is_blocklisted(db, raw.title)

                score = score_release(
                    title=raw.title,
                    quality=quality,
                    size=raw.size,
                    seeders=raw.seeders,
                    age_days=raw.age,
                    magazine_title=magazine.title,
                    profile_items=profile_items,
                )

                all_results.append(SearchResultResource(
                    guid=raw.guid,
                    title=raw.title,
                    indexer=indexer.name,
                    source=raw.indexer,
                    size=raw.size,
                    age=raw.age,
                    protocol=raw.protocol,
                    seeders=raw.seeders,
                    quality=quality,
                    language=language,
                    score=score,
                    is_blocklisted=blocked,
                    download_url=raw.download_url or "",
                    publish_date=raw.publish_date,
                ))
        except Exception:
            logger.warning("Search error for indexer %s", indexer.name, exc_info=True)

    all_results.sort(key=lambda r: r.score, reverse=True)
    return all_results


async def search_free(
    db: AsyncSession, query: str, config
) -> list[SearchResultResource]:
    """Free-text search across all enabled indexers (Prowlarr)."""
    from app.indexers.prowlarr import ProwlarrClient
    from app.models.indexer_config import IndexerConfig

    indexer_result = await db.execute(
        select(IndexerConfig).where(IndexerConfig.enabled.is_(True))
    )
    indexers = indexer_result.scalars().all()

    all_results: list[SearchResultResource] = []
    for indexer in indexers:
        try:
            client = ProwlarrClient(
                url=indexer.url,
                api_key=indexer.api_key,
            )
            raw_results = await client.search(query)
            for raw in raw_results:
                parsed = parse_magazine_filename(raw.title)
                quality = parsed.quality if parsed.quality != "unknown" else "unknown"
                language = parsed.language if parsed.language != "unknown" else "unknown"

                blocked = await is_blocklisted(db, raw.title)

                all_results.append(SearchResultResource(
                    guid=raw.guid,
                    title=raw.title,
                    indexer=indexer.name,
                    source=raw.indexer,
                    size=raw.size,
                    age=raw.age,
                    protocol=raw.protocol,
                    seeders=raw.seeders,
                    quality=quality,
                    language=language,
                    score=0.0,
                    is_blocklisted=blocked,
                    download_url=raw.download_url or "",
                    publish_date=raw.publish_date,
                ))
        except Exception:
            logger.warning("Search error for indexer %s", indexer.name, exc_info=True)

    return all_results


async def search_magazine_missing(
    db: AsyncSession, magazine_id: int, config
) -> dict[int, list[SearchResultResource]]:
    result = await db.execute(
        select(Issue).where(
            Issue.magazine_id == magazine_id,
            Issue.status.in_(["wanted"]),
            Issue.monitored.is_(True),
        )
    )
    wanted_issues = result.scalars().all()

    results_by_issue: dict[int, list[SearchResultResource]] = {}
    for issue in wanted_issues:
        results = await search_issue(db, issue.id, config)
        if results:
            results_by_issue[issue.id] = results
    return results_by_issue


def score_release(
    title: str,
    quality: str,
    size: int,
    seeders: int | None,
    age_days: int,
    magazine_title: str,
    profile_items: list[dict],
) -> float:
    score = 0.0

    # Title match (50 pts max)
    match = fuzzy_match_title(
        title,
        [magazine_title],
        threshold=50.0,
    )
    if match:
        _, match_score = match
        score += (match_score / 100.0) * 50.0

    # Quality vs profile (30 pts max)
    quality_rank = _QUALITY_INDEX.get(quality, 0)
    cutoff_rank = max(
        (
            _QUALITY_INDEX.get(item["quality"], 0)
            for item in profile_items
            if item.get("cutoff")
        ),
        default=3,
    )
    if cutoff_rank > 0:
        ratio = min(quality_rank / cutoff_rank, 1.0)
        score += ratio * 30.0

    # Size preference (10 pts max) - prefer 10-200MB
    size_mb = size / (1024 * 1024) if size > 0 else 0
    if 10 <= size_mb <= 200:
        score += 10.0
    elif 1 <= size_mb < 10:
        score += 5.0
    elif 200 < size_mb <= 500:
        score += 5.0
    elif size_mb > 500:
        score += 2.0

    # Seeds bonus (10 pts max)
    if seeders is not None and seeders > 0:
        score += min(math.log2(seeders + 1) * 2, 10.0)

    # Age bonus (newer = better, 10 pts max)
    age_penalty = min(age_days / 30.0, 10.0)
    score += 10.0 - age_penalty

    return round(score, 1)


def _build_query(magazine: Magazine, issue: Issue) -> str:
    terms = magazine.search_terms or magazine.title
    if issue.number is not None:
        return f"{terms} N{issue.number}"
    if issue.year and issue.month:
        return f"{terms} {issue.year} {issue.month:02d}"
    return terms


async def match_ia_results(
    db: AsyncSession,
    results: list[SearchResultResource],
    magazine_id: int,
) -> list[SearchResultResource]:
    """Compare IA results against wanted issues.

    Match by normalized title + date/number.
    Results that match a wanted issue get a score boost; non-matching results
    are kept but scored lower.
    """
    # Load magazine
    mag_result = await db.execute(
        select(Magazine).where(Magazine.id == magazine_id)
    )
    magazine = mag_result.scalars().first()
    if not magazine:
        return results

    # Load wanted issues for this magazine
    issue_result = await db.execute(
        select(Issue).where(
            Issue.magazine_id == magazine_id,
            Issue.status.in_(["wanted", "missing"]),
            Issue.monitored.is_(True),
        )
    )
    wanted_issues = issue_result.scalars().all()
    if not wanted_issues:
        return results

    scored: list[SearchResultResource] = []
    for result in results:
        parsed = parse_magazine_filename(result.title)
        match_score = 0.0

        # Check title similarity
        title_match = fuzzy_match_title(
            parsed.title, [magazine.title], threshold=60.0
        )
        if title_match:
            _, t_score = title_match
            match_score += (t_score / 100.0) * 50.0

        # Check if this matches a specific wanted issue
        for issue in wanted_issues:
            issue_matched = False

            # Match by number
            if (
                parsed.number is not None
                and issue.number is not None
                and parsed.number == issue.number
            ):
                issue_matched = True

            # Match by year + month
            if (
                not issue_matched
                and parsed.year is not None
                and parsed.month is not None
                and issue.year == parsed.year
                and issue.month == parsed.month
            ):
                issue_matched = True

            if issue_matched:
                match_score += 50.0
                break

        result.score = round(match_score, 1)
        scored.append(result)

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored


async def _get_quality_items(db: AsyncSession, profile_id: int | None) -> list[dict]:
    if profile_id is None:
        return []
    result = await db.execute(
        select(QualityProfileItem).where(
            QualityProfileItem.quality_profile_id == profile_id
        )
    )
    items = result.scalars().all()
    return [
        {
            "quality": item.quality,
            "allowed": item.allowed,
            "sort_order": item.sort_order,
        }
        for item in items
    ]
