"""PackPattern ORM model — learned torrent naming patterns."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PackPattern(Base):
    __tablename__ = "pack_pattern"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pack.id", ondelete="CASCADE"), nullable=False
    )
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uploader: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    pack = relationship("Pack", back_populates="patterns")

    __table_args__ = (Index("ix_pack_pattern_pack_id", "pack_id"),)
