"""Unified Activity table — remplace les trackers in-memory dispersés.

Toute action asynchrone visible dans l'UI passe par ce registre :
  - ``download``   : torrent/NZB en cours dans qBit/NZBget
  - ``direct_download`` : Anna's Archive / Internet Archive (téléchargement
                          direct pressarr)
  - ``import``     : post-download → parse + IA metadata + copy + cover
  - ``analyze``    : Re-analyze IA manuelle (Refresh IA)
  - ``scan``       : auto-grab scan (recherche + grab automatique)
  - ``scheduled``  : réservé — actions planifiées à venir

**Persistance** : survit aux redémarrages. Le monitoring reste
polling-based côté frontend, mais l'historique n'est plus perdu au
reboot. Rétention : cleanup asynchrone après ``retention_days``.

**Modularité** : le champ ``steps`` (JSON list) est libre — chaque
``kind`` définit sa propre séquence d'étapes. Ajouter un nouveau
type d'activité ne demande pas de migration.
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
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # « download | direct_download | import | analyze | scan | scheduled »
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # « queued | running | success | failed | cancelled »
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # Attachement optionnel — permet le filtrage par magazine/issue
    # depuis les pages détail. NULL quand l'activité ne cible rien de
    # précis (ex. scan global auto-grab).
    magazine_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("magazine.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Titre principal (« Le Figaro du 13 Aout 2026.pdf ») + sous-titre
    # optionnel (nom du download client, ID torrent, etc).
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 0 → 100 %. Sémantique dépend du kind :
    #   - download   : bytes reçus / total
    #   - import     : étapes franchies / total attendu
    #   - analyze    : idem
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Ligne d'état courante en français (« IA · OCR couverture — page 1/3 »).
    # Correspond au label de la dernière step pushée + hint éventuel.
    status_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Liste JSON ordonnée d'étapes franchies. Chaque step est
    # ``{step, label, hint?, at, elapsed_ms?, output?, error?}``.
    # C'est le fil chronologique complet — sert à l'affichage
    # timeline et au détail History.
    steps: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Métadonnées structurées libres — chaque kind définit sa forme.
    # Ex. download : {download_id, protocol, size_bytes, speed_bps, eta}.
    # Ex. import   : {file_name, source_dir}.
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ⚠️ Toujours utiliser un default Python (naive local time) —
    # ``server_default=func.now()`` écrit en UTC côté SQLite alors que
    # tout le service raisonne en ``datetime.now()`` (local). Le décalage
    # UTC↔local rendait toutes les activités « 2h dans le passé » côté
    # Python → cleanup_stale les tuait dès leur création.
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    # Timestamp de la dernière mise à jour (push_step / update_progress /
    # mark_done / mark_error). Sert au cleanup_stale : une activité qui
    # PUSH régulièrement (dispatch pack qui tourne 30 min sur 32
    # fichiers) ne doit pas être force-failed juste parce que
    # started_at > cutoff. Défault = started_at à la création.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_activity_status_kind", "status", "kind"),
        Index("ix_activity_started_at", "started_at"),
    )
