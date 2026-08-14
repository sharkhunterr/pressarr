"""Pack dispatch file ORM model.

Représente un fichier extrait d'un download de pack, en attente d'analyse
ou d'action utilisateur. Un pack_dispatch_file traverse plusieurs états :

  pending_analysis → analyzed → (pending_user | imported | ignored)
                              ↘ error

Le champ ``ai_run_id`` pointe vers l'enrichment_run qui a analysé le
fichier (mêmes steps que Refresh IA sur une issue). Le champ
``matched_magazine_id`` et ``proposed_magazine_data`` capturent la
décision automatique ; ``user_action_*`` capture l'override utilisateur.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PackDispatchFile(Base):
    __tablename__ = "pack_dispatch_file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pack.id", ondelete="CASCADE"), nullable=False
    )
    download_id: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    # Chemin absolu sur disque après extraction. Peut disparaître si le
    # torrent est supprimé du client — l'entrée reste pour l'audit trail.
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # pending_analysis | analyzed | pending_user | imported | ignored | error
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending_analysis"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Analyse IA — pointeur vers le run qui a produit la décision.
    ai_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_enrichment_run.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshot des metadata extraites (title, number, year, month, day, issn…).
    # Cache pour affichage rapide sans join sur enrichment_run.
    extracted_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Match automatique.
    matched_magazine_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("magazine.id", ondelete="SET NULL"), nullable=True
    )
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # parser | fuzzy | vision | arbiter | issn | manual — pour observabilité.
    match_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Si aucun match : proposition de magazine à créer (JSON).
    proposed_magazine_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Résolution utilisateur — override du match automatique.
    # create_magazine | assign_existing | ignore
    user_action: Mapped[str | None] = mapped_column(String(24), nullable=True)
    user_action_magazine_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("magazine.id", ondelete="SET NULL"), nullable=True
    )

    # Résultat de l'import (si status=imported).
    resolved_issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    pack = relationship("Pack")
    matched_magazine = relationship(
        "Magazine", foreign_keys=[matched_magazine_id]
    )
    user_action_magazine = relationship(
        "Magazine", foreign_keys=[user_action_magazine_id]
    )
    resolved_issue = relationship("Issue")

    __table_args__ = (
        Index("ix_pack_dispatch_file_pack_id", "pack_id"),
        Index("ix_pack_dispatch_file_download_id", "download_id"),
        Index("ix_pack_dispatch_file_status", "status"),
    )
