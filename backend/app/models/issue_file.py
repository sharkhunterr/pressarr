"""IssueFile ORM model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IssueFile(Base):
    __tablename__ = "issue_file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    magazine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("magazine.id", ondelete="CASCADE"), nullable=False
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
    # ─── Origine de l'import ─────────────────────────────────────
    # Trace la provenance de ce fichier — essentiel pour :
    #   - Re-analyse IA : recharge le bon "torrent_name" (pack file
    #     name vs torrent release title vs scene folder…).
    #   - UI issue detail : afficher "Importé depuis pack Journaux
    #     Nationaux le 15/08/2026" au lieu d'un blob opaque.
    #   - Diagnostic bug : "pourquoi cette issue s'est retrouvée là ?".
    #
    # ``source_type`` : torrent | pack | scene | ia | aa | manual
    # ``source_pack_id`` : FK Pack (nullable) — set uniquement quand
    #   source_type == 'pack'. NULL sinon.
    # ``source_release_title`` : release/pack title tel qu'il apparaît
    #   côté indexer/tracker. Pour torrent = nom du torrent, pour pack
    #   = nom du torrent du pack (pas du fichier interne — celui-ci
    #   est déjà dans original_filename).
    source_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="torrent", server_default="torrent"
    )
    source_pack_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pack.id", ondelete="SET NULL"), nullable=True
    )
    source_release_title: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    issue: Mapped["Issue | None"] = relationship(back_populates="file")
    magazine: Mapped["Magazine"] = relationship()
    source_pack: Mapped["Pack | None"] = relationship()
