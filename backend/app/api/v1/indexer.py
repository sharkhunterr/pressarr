"""Indexer configuration API routes — /api/v1/indexer."""

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
    IndexerTestResource,
    TestResult,
)

router = APIRouter(prefix="/api/v1/indexer", tags=["Indexers"])


@router.get("", response_model=list[IndexerConfigResource])
async def list_indexers(
    db: AsyncSession = Depends(get_db),
) -> list[IndexerConfigResource]:
    """List all indexer configurations (api_key excluded)."""
    result = await db.execute(select(IndexerConfig))
    indexers = result.scalars().all()
    return [IndexerConfigResource.model_validate(i) for i in indexers]


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
    )
    db.add(indexer)
    await db.flush()
    return IndexerConfigResource.model_validate(indexer)


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
    for field, value in update_data.items():
        setattr(indexer, field, value)

    await db.flush()
    return IndexerConfigResource.model_validate(indexer)


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
        is_valid, message = await client.test_connection()
        return TestResult(is_valid=is_valid, message=message)
    finally:
        await client.close()
