"""Magazine ORM model."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Magazine(Base):
    __tablename__ = "magazine"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    title_slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    issn: Mapped[str | None] = mapped_column(String(9), nullable=True, unique=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    monitored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    monitoring_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    search_terms: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    use_latest_issue_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    root_folder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("root_folder.id"), nullable=False
    )
    quality_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quality_profile.id"), nullable=False
    )
    metadata_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    last_searched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_metadata_refresh: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluded_days: Mapped[str | None] = mapped_column(String(20), nullable=True)

    root_folder: Mapped["RootFolder"] = relationship(back_populates="magazines")
    quality_profile: Mapped["QualityProfile"] = relationship(back_populates="magazines")
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="magazine", cascade="all, delete-orphan"
    )
    patterns: Mapped[list["MagazinePattern"]] = relationship(
        back_populates="magazine", cascade="all, delete-orphan"
    )
    rules: Mapped[list["MagazineRule"]] = relationship(
        back_populates="magazine", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_magazine_root_folder_id", "root_folder_id"),
        Index("ix_magazine_quality_profile_id", "quality_profile_id"),
    )
