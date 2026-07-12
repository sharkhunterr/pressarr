"""MagazinePattern ORM model — user-defined torrent naming patterns."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MagazinePattern(Base):
    __tablename__ = "magazine_pattern"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    magazine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("magazine.id", ondelete="CASCADE"), nullable=False
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

    magazine = relationship("Magazine", back_populates="patterns")

    __table_args__ = (Index("ix_magazine_pattern_magazine_id", "magazine_id"),)
