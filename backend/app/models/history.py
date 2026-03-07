"""History ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class History(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    magazine_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("magazine.id", ondelete="SET NULL"), nullable=True
    )
    issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue.id", ondelete="SET NULL"), nullable=True
    )
    pack_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pack.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_history_date", "date"),
        Index("ix_history_event_type", "event_type"),
        Index("ix_history_magazine_id", "magazine_id"),
        Index("ix_history_issue_id", "issue_id"),
        Index("ix_history_pack_id", "pack_id"),
        Index("ix_history_event_date", "event_type", "date"),
    )
