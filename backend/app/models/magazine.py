"""Magazine ORM model."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
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
    # Placeholder = magazine créé automatiquement (auto_create_missing_magazines
    # d'un pack) sur des metadata partielles. L'UI doit inviter l'utilisateur
    # à compléter (frequency, root folder, quality profile). Basculé à False
    # dès que l'utilisateur passe par le formulaire d'édition.
    is_placeholder: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Toggle per-magazine du pipeline wanted_search (Prowlarr + IA +
    # rules + auto-grab). False = skip toutes les issues de ce mag
    # dans le scheduler ET les auto-triggers. Les recherches manuelles
    # (bouton UI) restent possibles.
    wanted_search_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    # Tolérance en jours pour matcher une issue à un release. Défaut 0
    # (match strict day == day). Fallback simple si weekend_days ne
    # colle pas au cas d'usage.
    date_tolerance_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Jours de la semaine (0=Lundi ... 6=Dimanche) qui se REGROUPENT en
    # une seule issue "édition weekend". CSV, ex "5,6,0" = samedi +
    # dimanche + lundi combinés (cas Le Monde weekend). Filtre :
    # deux dates dont les weekdays tombent tous les deux dans ce set
    # ET sont dans la même semaine matchent la même issue.
    weekend_days: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None
    )
    # Tri des candidats envoyés au ranker IA par publish_date desc.
    # Défaut ON : les releases récents en premier — l'IA batch voit
    # d'abord les candidats plausibles (date proche de l'issue cible),
    # les vieilles rééditions arrivent en batches ultérieurs. Sur des
    # magazines exotiques où les uploaders re-publient sans MAJ date,
    # OFF conserve l'ordre python_score.
    sort_by_recent_date: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    # Override per-mag du plancher fuzzy titre (0-100). NULL = suit
    # le défaut global wanted_search_min_title_match. Utile pour un
    # magazine dont le nom est court/générique et cause faux négatifs
    # au seuil global (baisse à 70) — ou l'inverse, mag ambigu à
    # protéger (monte à 90).
    min_title_match_override: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    # Override per-mag du seuil composite auto-grab (0-100). NULL = suit
    # le défaut global wanted_search_auto_grab_threshold. Utile pour un
    # magazine facile à retrouver (baisse à 65) ou au contraire un mag
    # à titre générique où on veut être prudent (monte à 85).
    auto_grab_threshold_override: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
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
