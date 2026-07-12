"""QualityProfile and QualityProfileItem ORM models."""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QualityProfile(Base):
    __tablename__ = "quality_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    cutoff: Mapped[str] = mapped_column(String(20), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    items: Mapped[list["QualityProfileItem"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="QualityProfileItem.sort_order",
    )
    magazines: Mapped[list["Magazine"]] = relationship(back_populates="quality_profile")


class QualityProfileItem(Base):
    __tablename__ = "quality_profile_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quality_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quality_profile.id", ondelete="CASCADE"), nullable=False
    )
    quality: Mapped[str] = mapped_column(String(20), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    profile: Mapped["QualityProfile"] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("quality_profile_id", "quality", name="uq_profile_quality"),
        Index("ix_profile_item_order", "quality_profile_id", "sort_order"),
    )
