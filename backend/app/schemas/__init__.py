"""Pydantic v2 schemas with camelCase alias generation."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base model with camelCase JSON aliases (Art. II §2.1)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class PaginatedResource(CamelModel, Generic[T]):
    """Generic paginated response wrapper."""

    page: int
    page_size: int
    total_records: int
    records: list[T]
