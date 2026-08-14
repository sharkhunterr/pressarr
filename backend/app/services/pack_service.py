"""Pack management service — CRUD, patterns, rules, statistics.

Le pipeline d'extraction + analyse IA + dispatch a été déplacé dans
``pack_dispatch_service`` (bien plus riche que l'ancien fuzzy match sur
filename). Ce module ne contient plus que la gestion des packs eux-mêmes.
"""

import logging
import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.history import History
from app.models.pack import Pack
from app.models.pack_pattern import PackPattern
from app.models.pack_rule import PackRule
from app.services.magazine_service import generate_title_slug

logger = logging.getLogger(__name__)


# ---- CRUD ----


async def list_packs(
    db: AsyncSession,
    sort_key: str = "name",
    sort_dir: str = "asc",
    monitored: bool | None = None,
) -> list[Pack]:
    stmt = select(Pack).options(
        selectinload(Pack.patterns),
        selectinload(Pack.rules),
    )
    if monitored is not None:
        stmt = stmt.where(Pack.monitored == monitored)
    sort_column = getattr(Pack, sort_key, Pack.name)
    if sort_dir.lower() == "desc":
        sort_column = sort_column.desc()
    stmt = stmt.order_by(sort_column)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_pack(db: AsyncSession, pack_id: int) -> Pack | None:
    stmt = (
        select(Pack)
        .where(Pack.id == pack_id)
        .options(selectinload(Pack.patterns), selectinload(Pack.rules))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_pack(db: AsyncSession, data: dict) -> Pack:
    name = data["name"]
    name_slug = generate_title_slug(name)

    existing = await db.execute(select(Pack).where(Pack.name_slug == name_slug))
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Pack with slug '{name_slug}' already exists")

    pack = Pack(
        name=name,
        name_slug=name_slug,
        description=data.get("description"),
        search_query=data["search_query"],
        recurrence=data.get("recurrence", "none"),
        auto_search=data.get("auto_search", False),
        auto_grab=data.get("auto_grab", False),
        auto_import=data.get("auto_import", False),
        deep_ai_analysis=data.get("deep_ai_analysis", True),
        auto_create_missing_magazines=data.get("auto_create_missing_magazines", False),
        preview_before_import=data.get("preview_before_import", False),
        default_new_magazine_frequency=data.get("default_new_magazine_frequency", "weekly"),
        monitored=data.get("monitored", True),
        quality_profile_id=data["quality_profile_id"],
        root_folder_id=data["root_folder_id"],
    )
    db.add(pack)
    await db.flush()
    return pack


async def update_pack(db: AsyncSession, pack_id: int, data: dict) -> Pack | None:
    pack = await get_pack(db, pack_id)
    if pack is None:
        return None
    for key, value in data.items():
        if value is not None and hasattr(pack, key):
            setattr(pack, key, value)
    if "name" in data and data["name"] is not None:
        pack.name_slug = generate_title_slug(data["name"])
    await db.flush()
    return pack


async def delete_pack(db: AsyncSession, pack_id: int) -> bool:
    pack = await get_pack(db, pack_id)
    if pack is None:
        return False
    await db.delete(pack)
    await db.flush()
    return True


async def get_statistics(db: AsyncSession, pack_id: int) -> dict:
    pattern_count = (
        await db.execute(
            select(func.count(PackPattern.id)).where(PackPattern.pack_id == pack_id)
        )
    ).scalar() or 0

    rule_count = (
        await db.execute(
            select(func.count(PackRule.id)).where(PackRule.pack_id == pack_id)
        )
    ).scalar() or 0

    total_grabs = (
        await db.execute(
            select(func.count(History.id)).where(
                History.pack_id == pack_id,
                History.event_type == "grab",
            )
        )
    ).scalar() or 0

    last_grab = (
        await db.execute(
            select(History.date)
            .where(History.pack_id == pack_id, History.event_type == "grab")
            .order_by(History.date.desc())
            .limit(1)
        )
    ).scalar()

    return {
        "pattern_count": pattern_count,
        "rule_count": rule_count,
        "total_grabs": total_grabs,
        "last_grab_date": last_grab,
    }


# ---- Pattern management ----


async def add_pattern(db: AsyncSession, pack_id: int, data: dict) -> PackPattern:
    pattern = PackPattern(
        pack_id=pack_id,
        pattern=data["pattern"],
        source=data.get("source"),
        uploader=data.get("uploader"),
    )
    db.add(pattern)
    await db.flush()
    return pattern


async def delete_pattern(db: AsyncSession, pattern_id: int) -> bool:
    result = await db.execute(
        select(PackPattern).where(PackPattern.id == pattern_id)
    )
    pattern = result.scalar_one_or_none()
    if pattern is None:
        return False
    await db.delete(pattern)
    await db.flush()
    return True


async def learn_pattern_from_grab(
    db: AsyncSession, pack_id: int, torrent_title: str, indexer_name: str
) -> PackPattern:
    """Learn a pattern when user manually grabs a pack torrent.

    If an identical pattern exists, update last_seen_at instead of duplicating.
    """
    existing = await db.execute(
        select(PackPattern).where(
            PackPattern.pack_id == pack_id,
            PackPattern.pattern == torrent_title,
        )
    )
    existing_pattern = existing.scalar_one_or_none()
    if existing_pattern:
        existing_pattern.last_seen_at = datetime.now(UTC)
        await db.flush()
        return existing_pattern

    return await add_pattern(
        db,
        pack_id,
        {"pattern": torrent_title, "source": indexer_name},
    )


# ---- Rule management ----


async def add_rule(db: AsyncSession, pack_id: int, data: dict) -> PackRule:
    rule = PackRule(
        pack_id=pack_id,
        rule_type=data["rule_type"],
        pattern=data["pattern"],
    )
    db.add(rule)
    await db.flush()
    return rule


async def delete_rule(db: AsyncSession, rule_id: int) -> bool:
    result = await db.execute(select(PackRule).where(PackRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        return False
    await db.delete(rule)
    await db.flush()
    return True


def apply_rules(
    parsed_title: str, rules: list[PackRule]
) -> tuple[bool, str | None]:
    """Apply include/exclude rules to a parsed magazine title.

    Returns (excluded, reason).
    - If any exclude rule matches → excluded.
    - If include rules exist, must match at least one, otherwise excluded.
    """
    include_rules = [r for r in rules if r.rule_type == "include"]
    exclude_rules = [r for r in rules if r.rule_type == "exclude"]

    for rule in exclude_rules:
        if re.search(rule.pattern, parsed_title, re.IGNORECASE):
            return True, f"Excluded by rule: {rule.pattern}"

    if include_rules:
        for rule in include_rules:
            if re.search(rule.pattern, parsed_title, re.IGNORECASE):
                return False, None
        return True, "No include rule matched"

    return False, None


# NOTE : Extraction, listing des fichiers, preview/dispatch et import
# sont maintenant gérés par ``pack_dispatch_service`` — pipeline complet
# avec IA vision + arbiter + création de magazine placeholder.
