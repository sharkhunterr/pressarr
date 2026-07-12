"""Quality profile Pydantic schemas."""

from app.schemas import CamelModel


class QualityProfileItemResource(CamelModel):
    """A single quality level within a profile."""

    id: int | None = None
    quality: str
    allowed: bool
    sort_order: int


class QualityProfileResource(CamelModel):
    """Response schema for a quality profile."""

    id: int
    name: str
    cutoff: str
    is_default: bool
    items: list[QualityProfileItemResource] = []


class QualityProfileCreateResource(CamelModel):
    """Request schema to create a quality profile."""

    name: str
    cutoff: str
    is_default: bool = False
    items: list[QualityProfileItemResource] = []


class QualityProfileUpdateResource(CamelModel):
    """Request schema to update a quality profile."""

    name: str | None = None
    cutoff: str | None = None
    is_default: bool | None = None
    items: list[QualityProfileItemResource] | None = None
