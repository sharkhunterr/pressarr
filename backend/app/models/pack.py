"""Pack ORM model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Pack(Base):
    __tablename__ = "pack"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_query: Mapped[str] = mapped_column(String(500), nullable=False)
    recurrence: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none"
    )
    auto_search: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_grab: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_import: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Deep analysis = full IA pipeline (torrent → python-OCR → vision → arbiter)
    # sur chaque fichier extrait. False = parser filename uniquement (10× plus
    # rapide, moins précis).
    deep_ai_analysis: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    # ON = matches faibles/absents → magazine placeholder auto-créé + import.
    # OFF = ces fichiers restent en pending_user pour décision manuelle.
    auto_create_missing_magazines: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # ON = rien n'est jamais auto-importé, tous les fichiers passent par
    # l'onglet Dispatch pour validation utilisateur.
    preview_before_import: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Fréquence par défaut appliquée aux magazines placeholder auto-créés.
    default_new_magazine_frequency: Mapped[str] = mapped_column(
        String(20), nullable=False, default="weekly", server_default="weekly"
    )
    monitored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quality_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quality_profile.id"), nullable=False
    )
    root_folder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("root_folder.id"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    last_searched_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Relationships
    quality_profile = relationship("QualityProfile")
    root_folder = relationship("RootFolder")
    patterns: Mapped[list["PackPattern"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan"
    )
    rules: Mapped[list["PackRule"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_pack_name_slug", "name_slug"),
        Index("ix_pack_quality_profile_id", "quality_profile_id"),
        Index("ix_pack_root_folder_id", "root_folder_id"),
    )
