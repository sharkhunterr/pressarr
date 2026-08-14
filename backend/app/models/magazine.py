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
    # 'subscription' (default, recurring) | 'one_shot' (single
    # back-issue, no further monitoring). The auto-grab
    # scheduler reads this to decide whether to keep scanning
    # indexers after the first successful grab.
    request_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="subscription",
        server_default="subscription",
    )
    # One-shot target — populated only when ``request_type``
    # is ``one_shot``. Either an operator-typed issue identifier
    # ("N°594", "HS 14", "594") or a publication date (used for
    # dailies like L'Équipe where issues are not numbered).
    target_issue_label: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    target_issue_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
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
    # Weekday on which the magazine hits newsstands, ISO indexing
    # (0=Monday … 6=Sunday). Used by the forecast generator to snap
    # weekly/biweekly upcoming issues to the correct day even when
    # no real issue exists yet to seed the rhythm — e.g. Paris Match
    # = 3 (Thursday) means every forecast lands on a Thursday
    # regardless of the monitoring start date. NULL = infer from
    # last real issue (or monitoring_start_date).
    release_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Custom crop zones pour l'IA vision, JSON array. Format canonique
    # (nouveau) : list of dicts. Chaque dict = un rectangle en ratios
    # 0..1 avec rotation optionnelle qui sera appliquée AVANT envoi
    # à la vision (utile pour les bandeaux verticaux type tarif Paris
    # Match dont le texte est écrit à 90°) :
    #   [{"x":0.05,"y":0.02,"w":0.9,"h":0.15,"rotation":0,"label":"masthead"},
    #    {"x":0.0,"y":0.2,"w":0.04,"h":0.8,"rotation":90,"label":"tarif"}]
    # Rétro-compat : un dict unique legacy `{"x":..,"y":..,"w":..,"h":..}`
    # est promu automatiquement en `[{...}]` par ``_lookup_magazine_crop``.
    # Null = pas de crop custom, fallback sur ``ai_enrichment_vision_crop``.
    # TEXT au lieu de VARCHAR(200) — 4+ zones dépassent facilement la
    # limite précédente. Migration heal-at-boot upgrade des rows old.
    ai_crop_rect: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ISSN-first cascade enrichment (populated by ZDB / Wikidata / BnF / LoC
    # via app.metadata.cascade). All nullable — the cascade is best-effort
    # and rarely fills everything.
    language: Mapped[str | None] = mapped_column(String(2), nullable=True)
    wikidata_qid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    zdb_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    wikipedia_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Comma-separated coarse labels: press, newspaper, scientific, sports, …
    categories: Mapped[str | None] = mapped_column(String(500), nullable=True)
    first_issued: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ceased_at: Mapped[str | None] = mapped_column(String(10), nullable=True)
    enrichment_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )

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
