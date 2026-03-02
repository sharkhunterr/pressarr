"""Quality profile service — pure helpers and async CRUD."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quality_profile import QualityProfile, QualityProfileItem
from app.schemas.quality import (
    QualityProfileCreateResource,
    QualityProfileUpdateResource,
)

# Ordered from lowest to highest quality.
QUALITY_ORDER: list[str] = [
    "unknown",
    "scan",
    "pdf_lq",
    "pdf_hq",
    "retail",
    "truepdf",
]

_QUALITY_INDEX: dict[str, int] = {q: i for i, q in enumerate(QUALITY_ORDER)}


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def compare_quality(a: str, b: str) -> int:
    """Compare two quality values.

    Returns negative if *a* < *b*, 0 if equal, positive if *a* > *b*.
    Unknown quality strings are treated as index -1 (below everything).
    """
    idx_a = _QUALITY_INDEX.get(a, -1)
    idx_b = _QUALITY_INDEX.get(b, -1)
    return idx_a - idx_b


def is_at_cutoff(quality: str, profile: QualityProfile) -> bool:
    """Return ``True`` if *quality* meets or exceeds the profile's cutoff."""
    return compare_quality(quality, profile.cutoff) >= 0


def should_upgrade(
    current_quality: str,
    new_quality: str,
    profile: QualityProfile,
) -> bool:
    """Determine whether a file should be upgraded.

    An upgrade is warranted when:
    1. The current quality is below the profile's cutoff, AND
    2. The new quality is strictly better than the current quality, AND
    3. The new quality is allowed in the profile.
    """
    if is_at_cutoff(current_quality, profile):
        return False
    if compare_quality(new_quality, current_quality) <= 0:
        return False
    # Check that the new quality is allowed in the profile.
    allowed_qualities = {
        item.quality for item in profile.items if item.allowed
    }
    return new_quality in allowed_qualities


# ---------------------------------------------------------------------------
# Async CRUD operations
# ---------------------------------------------------------------------------

async def list_profiles(db: AsyncSession) -> list[QualityProfile]:
    """Return all quality profiles with their items eagerly loaded."""
    result = await db.execute(
        select(QualityProfile)
        .options(selectinload(QualityProfile.items))
        .order_by(QualityProfile.id)
    )
    return list(result.scalars().all())


async def get_profile(db: AsyncSession, profile_id: int) -> QualityProfile | None:
    """Return a single quality profile by ID, or ``None``."""
    result = await db.execute(
        select(QualityProfile)
        .where(QualityProfile.id == profile_id)
        .options(selectinload(QualityProfile.items))
    )
    return result.scalars().first()


async def create_profile(
    db: AsyncSession,
    data: QualityProfileCreateResource,
) -> QualityProfile:
    """Create a new quality profile with its items."""
    profile = QualityProfile(
        name=data.name,
        cutoff=data.cutoff,
        is_default=data.is_default,
    )

    # If this profile is marked as default, unset any existing default.
    if data.is_default:
        await _unset_default(db)

    db.add(profile)
    await db.flush()  # Populate profile.id

    for item_data in data.items:
        item = QualityProfileItem(
            quality_profile_id=profile.id,
            quality=item_data.quality,
            allowed=item_data.allowed,
            sort_order=item_data.sort_order,
        )
        db.add(item)

    await db.flush()

    # Re-fetch with items eagerly loaded so the caller gets a complete object.
    return await get_profile(db, profile.id)  # type: ignore[return-value]


async def update_profile(
    db: AsyncSession,
    profile_id: int,
    data: QualityProfileUpdateResource,
) -> QualityProfile | None:
    """Update an existing quality profile. Returns ``None`` if not found."""
    profile = await get_profile(db, profile_id)
    if profile is None:
        return None

    if data.name is not None:
        profile.name = data.name
    if data.cutoff is not None:
        profile.cutoff = data.cutoff
    if data.is_default is not None:
        if data.is_default and not profile.is_default:
            await _unset_default(db)
        profile.is_default = data.is_default

    if data.items is not None:
        # Replace all items: delete existing, add new.
        profile.items.clear()
        await db.flush()

        for item_data in data.items:
            item = QualityProfileItem(
                quality_profile_id=profile.id,
                quality=item_data.quality,
                allowed=item_data.allowed,
                sort_order=item_data.sort_order,
            )
            db.add(item)

    await db.flush()
    return await get_profile(db, profile_id)


async def delete_profile(db: AsyncSession, profile_id: int) -> bool:
    """Delete a quality profile.

    Returns ``False`` if the profile is in use by magazines (preventing
    deletion) or if the profile does not exist.
    """
    profile = await get_profile(db, profile_id)
    if profile is None:
        return False

    # Prevent deletion if magazines reference this profile.
    from app.models.magazine import Magazine

    result = await db.execute(
        select(Magazine.id).where(Magazine.quality_profile_id == profile_id).limit(1)
    )
    if result.scalars().first() is not None:
        return False

    await db.delete(profile)
    await db.flush()
    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _unset_default(db: AsyncSession) -> None:
    """Clear the ``is_default`` flag on all existing profiles."""
    result = await db.execute(
        select(QualityProfile).where(QualityProfile.is_default.is_(True))
    )
    for p in result.scalars().all():
        p.is_default = False
