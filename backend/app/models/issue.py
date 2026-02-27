"""Issue ORM model."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Issue(Base):
    __tablename__ = "issue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    magazine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("magazine.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="missing")
    monitored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_special: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_forecast: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cover_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    magazine: Mapped["Magazine"] = relationship(back_populates="issues")
    file: Mapped["IssueFile | None"] = relationship(
        back_populates="issue", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("magazine_id", "number", name="uq_issue_magazine_number"),
        Index("ix_issue_magazine_date", "magazine_id", "publication_date"),
        Index("ix_issue_status", "status"),
        Index("ix_issue_magazine_id", "magazine_id"),
    )
