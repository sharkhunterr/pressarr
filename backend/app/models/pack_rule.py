"""PackRule ORM model — include/exclude rules for dispatch."""

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PackRule(Base):
    __tablename__ = "pack_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pack.id", ondelete="CASCADE"), nullable=False
    )
    rule_type: Mapped[str] = mapped_column(String(10), nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)

    pack = relationship("Pack", back_populates="rules")

    __table_args__ = (Index("ix_pack_rule_pack_id", "pack_id"),)
