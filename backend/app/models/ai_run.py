"""AI run models — traces both metadata enrichment and search ranker.

Both tables are append-only journals : one row per pipeline execution
(enrichment run OR ranker run). They serve three purposes :
  1. Debug — full raw outputs of each LLM step are stored so the
     operator can see WHY an arbiter picked a value.
  2. Cache — enrichment is keyed on (magazine_id, pdf_hash) ; the
     latest successful row for that key is treated as authoritative
     and skipped by subsequent runs unless the file changes.
  3. History UI — the timeline surfaces these events with an
     expandable detail panel.
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


class AIEnrichmentRun(Base):
    """One full enrichment pipeline execution.

    ``steps_json`` holds the per-step outputs as a JSON array :
      [{"step": "text", "model": "mistral:7b", "output": {...},
        "elapsed_ms": 4210, "error": null},
       {"step": "vision", "page": 1, "model": "minicpm-v:8b",
        "output": {...}, "elapsed_ms": 12800, "error": null},
       ...]

    ``final_json`` = the arbiter's merged result, exactly what was
    written back to the magazine/issue (or stored as proposal).
    ``applied_mode`` = the ``ai_enrichment_mode`` in effect at run
    time (may differ later if the operator changes settings).
    """

    __tablename__ = "ai_enrichment_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    magazine_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("magazine.id", ondelete="SET NULL"),
        nullable=True,
    )
    issue_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("issue.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Trigger context : "grab_auto" | "import_manual" | "reanalyze"
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    # SHA-256 of the PDF binary (or empty string when no file — text-
    # only enrichment). Combined with magazine_id = cache key.
    pdf_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    # "remplace" | "complete" | "propose" | "skipped_fallback"
    applied_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    steps_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    final_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_ai_enrichment_magazine_hash", "magazine_id", "pdf_hash"),
        Index("ix_ai_enrichment_started", "started_at"),
    )


class AIRankerRun(Base):
    """One search ranker execution.

    ``candidates_json`` = the exact ordered list sent to the ranker
    (top_k from the native scorer). ``batches_json`` = raw outputs
    per batch. ``final_json`` = {picked_index, confidence, reason}
    of the round-of-1.

    ``scorer_top_index`` and ``ai_picked_index`` refer to positions
    in ``candidates_json`` so the operator can see when the two
    disagreed. ``applied_mode`` = ranker mode in effect at run time
    (``ai_wins`` | ``ai_veto_only`` | ``ai_advisory``).
    """

    __tablename__ = "ai_ranker_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    magazine_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("magazine.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Pattern that triggered the search (magazine or pack pattern id).
    pattern_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Cache key = SHA-256 of the sorted candidate URLs/GUIDs.
    candidates_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    applied_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    model_used: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    candidates_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    batches_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    final_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    scorer_top_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_picked_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_ai_ranker_pattern_hash", "pattern_id", "candidates_hash"),
        Index("ix_ai_ranker_started", "started_at"),
    )


class AIEnrichmentProposal(Base):
    """Enrichment propositions awaiting user validation.

    Populated only when ``ai_enrichment_mode == "propose"``. The
    magazine/issue is NOT modified — the operator reviews and
    accepts (writes to DB) or rejects (deletes the row) via the UI.
    """

    __tablename__ = "ai_enrichment_proposal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    magazine_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("magazine.id", ondelete="CASCADE"),
        nullable=True,
    )
    issue_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("issue.id", ondelete="CASCADE"),
        nullable=True,
    )
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_enrichment_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposed_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_ai_proposal_magazine_status", "magazine_id", "status"),
    )
