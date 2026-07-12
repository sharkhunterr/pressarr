"""Quality Profile API routes — /api/v1/qualityprofile."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.quality import (
    QualityProfileCreateResource,
    QualityProfileResource,
    QualityProfileUpdateResource,
)
from app.services import quality_service

router = APIRouter(prefix="/api/v1/qualityprofile", tags=["Quality Profiles"])


@router.get("", response_model=list[QualityProfileResource])
async def list_profiles(
    db: AsyncSession = Depends(get_db),
) -> list[QualityProfileResource]:
    """List all quality profiles."""
    profiles = await quality_service.list_profiles(db)
    return [QualityProfileResource.model_validate(p) for p in profiles]


@router.get("/{profile_id}", response_model=QualityProfileResource)
async def get_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
) -> QualityProfileResource:
    """Get a single quality profile with its items."""
    profile = await quality_service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Quality profile not found")
    return QualityProfileResource.model_validate(profile)


@router.post("", response_model=QualityProfileResource, status_code=201)
async def create_profile(
    data: QualityProfileCreateResource,
    db: AsyncSession = Depends(get_db),
) -> QualityProfileResource:
    """Create a new quality profile."""
    profile = await quality_service.create_profile(db, data)
    return QualityProfileResource.model_validate(profile)


@router.put("/{profile_id}", response_model=QualityProfileResource)
async def update_profile(
    profile_id: int,
    data: QualityProfileUpdateResource,
    db: AsyncSession = Depends(get_db),
) -> QualityProfileResource:
    """Update an existing quality profile."""
    profile = await quality_service.update_profile(db, profile_id, data)
    if profile is None:
        raise HTTPException(status_code=404, detail="Quality profile not found")
    return QualityProfileResource.model_validate(profile)


@router.delete("/{profile_id}", status_code=200)
async def delete_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a quality profile. Returns 409 if profile is in use by magazines."""
    profile = await quality_service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Quality profile not found")

    deleted = await quality_service.delete_profile(db, profile_id)
    if not deleted:
        raise HTTPException(
            status_code=409,
            detail="Quality profile is in use by one or more magazines and cannot be deleted",
        )
    return {"ok": True}
