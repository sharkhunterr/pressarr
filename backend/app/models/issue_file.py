"""IssueFile ORM model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IssueFile(Base):
    __tablename__ = "issue_file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issue.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    path: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    relative_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    quality: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    release_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language: Mapped[str | None] = mapped_column(String(5), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    issue: Mapped["Issue"] = relationship(back_populates="file")
