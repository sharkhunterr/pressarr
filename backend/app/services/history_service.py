"""History event tracking and blocklist management."""

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocklist import Blocklist
from app.models.history import History

logger = logging.getLogger(__name__)


async def create_event(
    db: AsyncSession,
    event_type: str,
    magazine_id: int | None = None,
    issue_id: int | None = None,
    details: str | None = None,
    data: dict | None = None,
) -> History:
    event = History(
        event_type=event_type,
        magazine_id=magazine_id,
        issue_id=issue_id,
        details=details,
        data=json.dumps(data) if data else None,
    )
    db.add(event)
    await db.flush()
    return event


async def list_events(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    event_type: str | None = None,
    magazine_id: int | None = None,
) -> tuple[list[History], int]:
    query = select(History)
    count_query = select(func.count(History.id))

    if event_type:
        query = query.where(History.event_type == event_type)
        count_query = count_query.where(History.event_type == event_type)
    if magazine_id:
        query = query.where(History.magazine_id == magazine_id)
        count_query = count_query.where(History.magazine_id == magazine_id)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(History.date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def purge_old_events(db: AsyncSession, retention_days: int = 365) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    result = await db.execute(
        delete(History).where(History.date < cutoff)
    )
    return result.rowcount


async def list_blocklist(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    magazine_id: int | None = None,
) -> tuple[list[Blocklist], int]:
    query = select(Blocklist)
    count_query = select(func.count(Blocklist.id))

    if magazine_id:
        query = query.where(Blocklist.magazine_id == magazine_id)
        count_query = count_query.where(Blocklist.magazine_id == magazine_id)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Blocklist.date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def add_to_blocklist(
    db: AsyncSession,
    release_title: str,
    magazine_id: int | None = None,
    issue_id: int | None = None,
    indexer: str | None = None,
    protocol: str | None = None,
    reason: str | None = None,
) -> Blocklist:
    entry = Blocklist(
        release_title=release_title,
        magazine_id=magazine_id,
        issue_id=issue_id,
        indexer=indexer,
        protocol=protocol,
        reason=reason,
    )
    db.add(entry)
    await db.flush()
    return entry


async def remove_from_blocklist(db: AsyncSession, blocklist_id: int) -> bool:
    result = await db.execute(
        select(Blocklist).where(Blocklist.id == blocklist_id)
    )
    entry = result.scalars().first()
    if not entry:
        return False
    await db.delete(entry)
    return True


async def bulk_remove_from_blocklist(db: AsyncSession, ids: list[int]) -> int:
    result = await db.execute(
        delete(Blocklist).where(Blocklist.id.in_(ids))
    )
    return result.rowcount


async def is_blocklisted(db: AsyncSession, release_title: str) -> bool:
    result = await db.execute(
        select(func.count(Blocklist.id)).where(
            Blocklist.release_title == release_title
        )
    )
    return (result.scalar() or 0) > 0
