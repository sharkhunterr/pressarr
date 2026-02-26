"""Blocklist ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Blocklist(Base):
    __tablename__ = "blocklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    magazine_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("magazine.id", ondelete="CASCADE"), nullable=True
    )
    issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue.id", ondelete="SET NULL"), nullable=True
    )
    release_title: Mapped[str] = mapped_column(String(500), nullable=False)
    indexer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_blocklist_release_title", "release_title"),
        Index("ix_blocklist_magazine_id", "magazine_id"),
    )
