"""MagazineRule ORM model — include/exclude rules for RSS matching."""

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MagazineRule(Base):
    __tablename__ = "magazine_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    magazine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("magazine.id", ondelete="CASCADE"), nullable=False
    )
    rule_type: Mapped[str] = mapped_column(String(10), nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)

    magazine = relationship("Magazine", back_populates="rules")

    __table_args__ = (Index("ix_magazine_rule_magazine_id", "magazine_id"),)
