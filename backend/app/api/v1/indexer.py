"""Indexer configuration API routes — /api/v1/indexer."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.indexers.prowlarr import ProwlarrClient
from app.models.indexer_config import IndexerConfig
from app.schemas.download import (
    IndexerConfigCreateResource,
    IndexerConfigResource,
    IndexerConfigUpdateResource,
    IndexerOverrideEntry,
    IndexerTestResource,
    TestResult,
)

router = APIRouter(prefix="/api/v1/indexer", tags=["Indexers"])


def _parse_overrides(raw: str) -> dict[str, IndexerOverrideEntry]:
    """Parse JSON text into override dict."""
    try:
        data = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        data = {}
    return {k: IndexerOverrideEntry(**v) if isinstance(v, dict) else v for k, v in data.items()}


def _serialize_overrides(overrides: dict[str, IndexerOverrideEntry]) -> str:
    """Serialize override dict to JSON text."""
    return json.dumps({k: v.model_dump() for k, v in overrides.items()})


def _to_resource(indexer: IndexerConfig) -> IndexerConfigResource:
    """Convert ORM model to response schema, parsing JSON overrides."""
    return IndexerConfigResource(
        id=indexer.id,
        name=indexer.name,
        url=indexer.url,
        api_key=indexer.api_key,
        categories=indexer.categories,
        enabled=indexer.enabled,
        indexer_overrides=_parse_overrides(indexer.indexer_overrides),
    )


@router.get("", response_model=list[IndexerConfigResource])
async def list_indexers(
    db: AsyncSession = Depends(get_db),
) -> list[IndexerConfigResource]:
    """List all indexer configurations (api_key excluded)."""
    result = await db.execute(select(IndexerConfig))
    indexers = result.scalars().all()
    return [_to_resource(i) for i in indexers]


@router.post("", response_model=IndexerConfigResource, status_code=201)
async def create_indexer(
    body: IndexerConfigCreateResource,
    db: AsyncSession = Depends(get_db),
) -> IndexerConfigResource:
    """Create a new indexer configuration."""
    indexer = IndexerConfig(
        name=body.name,
        url=body.url,
        api_key=body.api_key,
        categories=body.categories,
        enabled=body.enabled,
        indexer_overrides=_serialize_overrides(body.indexer_overrides),
    )
    db.add(indexer)
    await db.flush()
    return _to_resource(indexer)


@router.put("/{indexer_id}", response_model=IndexerConfigResource)
async def update_indexer(
    indexer_id: int,
    body: IndexerConfigUpdateResource,
    db: AsyncSession = Depends(get_db),
) -> IndexerConfigResource:
    """Update an existing indexer configuration."""
    indexer = await db.get(IndexerConfig, indexer_id)
    if not indexer:
        raise HTTPException(status_code=404, detail="Indexer not found")

    update_data = body.model_dump(exclude_unset=True)
    if "indexer_overrides" in update_data and update_data["indexer_overrides"] is not None:
        overrides = {
            k: IndexerOverrideEntry(**(v if isinstance(v, dict) else v.model_dump()))
            for k, v in update_data.pop("indexer_overrides").items()
        }
        indexer.indexer_overrides = _serialize_overrides(overrides)

    for field, value in update_data.items():
        setattr(indexer, field, value)

    await db.flush()
    return _to_resource(indexer)


@router.delete("/{indexer_id}", status_code=204)
async def delete_indexer(
    indexer_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an indexer configuration."""
    indexer = await db.get(IndexerConfig, indexer_id)
    if not indexer:
        raise HTTPException(status_code=404, detail="Indexer not found")
    await db.delete(indexer)
    await db.flush()


@router.post("/test", response_model=TestResult)
async def test_indexer(
    body: IndexerTestResource,
) -> TestResult:
    """Test connection to a Prowlarr instance."""
    client = ProwlarrClient(url=body.url, api_key=body.api_key)
    try:
        is_valid, message, indexers = await client.test_connection()
        return TestResult(is_valid=is_valid, message=message, indexers=indexers)
    finally:
        await client.close()


@router.post("/{indexer_id}/test", response_model=TestResult)
async def test_indexer_by_id(
    indexer_id: int,
    db: AsyncSession = Depends(get_db),
) -> TestResult:
    """Test connection using stored credentials."""
    indexer = await db.get(IndexerConfig, indexer_id)
    if not indexer:
        raise HTTPException(status_code=404, detail="Indexer not found")
    client = ProwlarrClient(url=indexer.url, api_key=indexer.api_key)
    try:
        is_valid, message, indexers = await client.test_connection()
        return TestResult(is_valid=is_valid, message=message, indexers=indexers)
    finally:
        await client.close()
