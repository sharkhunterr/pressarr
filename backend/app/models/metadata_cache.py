"""MetadataCache ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetadataCache(Base):
    __tablename__ = "metadata_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(500), nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "cache_key", name="uq_metadata_cache_provider_key"),
        Index("ix_metadata_cache_expires", "expires_at"),
    )
