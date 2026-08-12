"""AI-related endpoints — settings, Ollama probe, re-analyze, history detail."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_config
from app.models.ai_run import (
    AIEnrichmentProposal,
    AIEnrichmentRun,
    AIRankerRun,
)
from app.models.issue import Issue
from app.models.issue_file import IssueFile
from app.models.magazine import Magazine
from app.schemas import CamelModel
from app.services.ai_enrichment_service import (
    AIEnrichmentService,
    merge_ai_into_parsed,
)
from app.services.ai_ollama_adapter import OllamaAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI"])


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class AISettingsResource(CamelModel):
    ollama_url: str
    ollama_timeout_s: int
    enrichment_enabled: bool
    enrichment_mode: str  # remplace | complete | propose
    enrichment_vision_pages: list[int]
    text_model: str
    vision_model: str
    text_prompt: str
    vision_prompt: str
    arbiter_prompt: str
    ranker_enabled: bool
    ranker_mode: str  # ai_wins | ai_veto_only | ai_advisory
    ranker_batch_size: int
    ranker_top_k: int
    ranker_confidence_threshold: float
    ranker_prompt: str


class AISettingsUpdateResource(CamelModel):
    ollama_url: str | None = None
    ollama_timeout_s: int | None = None
    enrichment_enabled: bool | None = None
    enrichment_mode: str | None = None
    enrichment_vision_pages: list[int] | None = None
    text_model: str | None = None
    vision_model: str | None = None
    text_prompt: str | None = None
    vision_prompt: str | None = None
    arbiter_prompt: str | None = None
    ranker_enabled: bool | None = None
    ranker_mode: str | None = None
    ranker_batch_size: int | None = None
    ranker_top_k: int | None = None
    ranker_confidence_threshold: float | None = None
    ranker_prompt: str | None = None


def _to_resource(config) -> AISettingsResource:
    return AISettingsResource(
        ollama_url=config.ai_ollama_url,
        ollama_timeout_s=config.ai_ollama_timeout_s,
        enrichment_enabled=config.ai_enrichment_enabled,
        enrichment_mode=config.ai_enrichment_mode,
        enrichment_vision_pages=config.ai_enrichment_vision_pages,
        text_model=config.ai_text_model,
        vision_model=config.ai_vision_model,
        text_prompt=config.ai_text_prompt,
        vision_prompt=config.ai_vision_prompt,
        arbiter_prompt=config.ai_arbiter_prompt,
        ranker_enabled=config.ai_ranker_enabled,
        ranker_mode=config.ai_ranker_mode,
        ranker_batch_size=config.ai_ranker_batch_size,
        ranker_top_k=config.ai_ranker_top_k,
        ranker_confidence_threshold=config.ai_ranker_confidence_threshold,
        ranker_prompt=config.ai_ranker_prompt,
    )


@router.get("/settings", response_model=AISettingsResource)
async def get_ai_settings(config=Depends(get_config)):
    return _to_resource(config)


@router.post("/settings", response_model=AISettingsResource)
async def save_ai_settings(
    body: AISettingsUpdateResource,
    config=Depends(get_config),
):
    """Update AI settings ; every field is optional (partial patch)."""
    valid_enrich_modes = {"remplace", "complete", "propose"}
    valid_ranker_modes = {"ai_wins", "ai_veto_only", "ai_advisory"}

    if body.enrichment_mode is not None and body.enrichment_mode not in valid_enrich_modes:
        raise HTTPException(400, f"Invalid enrichment mode; must be {valid_enrich_modes}")
    if body.ranker_mode is not None and body.ranker_mode not in valid_ranker_modes:
        raise HTTPException(400, f"Invalid ranker mode; must be {valid_ranker_modes}")

    fields_map = {
        "ollama_url": "ai_ollama_url",
        "ollama_timeout_s": "ai_ollama_timeout_s",
        "enrichment_enabled": "ai_enrichment_enabled",
        "enrichment_mode": "ai_enrichment_mode",
        "enrichment_vision_pages": "ai_enrichment_vision_pages",
        "text_model": "ai_text_model",
        "vision_model": "ai_vision_model",
        "text_prompt": "ai_text_prompt",
        "vision_prompt": "ai_vision_prompt",
        "arbiter_prompt": "ai_arbiter_prompt",
        "ranker_enabled": "ai_ranker_enabled",
        "ranker_mode": "ai_ranker_mode",
        "ranker_batch_size": "ai_ranker_batch_size",
        "ranker_top_k": "ai_ranker_top_k",
        "ranker_confidence_threshold": "ai_ranker_confidence_threshold",
        "ranker_prompt": "ai_ranker_prompt",
    }
    for body_field, cfg_field in fields_map.items():
        value = getattr(body, body_field)
        if value is not None:
            setattr(config, cfg_field, value)
    config.save()
    return _to_resource(config)


# ---------------------------------------------------------------------------
# Ollama probe — models list + reachability
# ---------------------------------------------------------------------------


class OllamaModelsResource(CamelModel):
    reachable: bool
    url: str
    models: list[str]
    error: str | None = None


@router.get("/ollama/models", response_model=OllamaModelsResource)
async def list_ollama_models(
    url: str | None = None,
    config=Depends(get_config),
):
    """Probe an Ollama server. Populates UI dropdowns.

    ``url`` : optional query param — pass the currently-edited URL
    (before save) so the "Test" button in the settings UI probes the
    field's live value instead of the persisted config. Falls back
    to ``config.ai_ollama_url`` when not provided.
    """
    target = url or config.ai_ollama_url
    adapter = OllamaAdapter(target, timeout_s=10)
    try:
        models = await adapter.list_models()
        return OllamaModelsResource(
            reachable=True, url=adapter.url, models=models
        )
    except Exception as exc:  # noqa: BLE001
        return OllamaModelsResource(
            reachable=False, url=adapter.url, models=[], error=str(exc)
        )


# ---------------------------------------------------------------------------
# Re-analyze a specific magazine
# ---------------------------------------------------------------------------


class ReanalyzeRequest(CamelModel):
    issue_id: int | None = None  # if None → most recent issue file
    apply_result: bool = True  # if False, only run + return, don't write


class ReanalyzeResponse(CamelModel):
    run_id: int
    applied_mode: str
    final: dict
    steps: list[dict]
    total_elapsed_ms: int


class BatchRefreshRequest(CamelModel):
    """Selector for the "refresh with AI" bulk operation.

    Empty ``issue_ids`` → all issues of the magazine that have a file.
    ``sources`` chooses which enrichment layers run per issue. Order
    of execution :
      1. `metadata` : classic providers refresh (Google Books,
         Internet Archive, Anna's Archive — same as the existing
         magazine refresh button)
      2. `ai_text`  : text LLM on the original torrent name
      3. `ai_vision`: vision LLM on the configured cover pages
    Each toggle is independent — the user can pick, say, only AI
    vision to re-OCR a bunch of covers without re-hitting TMDB.
    """

    issue_ids: list[int] = []
    include_metadata: bool = True
    include_ai_text: bool = True
    include_ai_vision: bool = True
    apply_result: bool = True
    # Défaut True : le user a explicitement cliqué « Refresh IA »,
    # il attend une vraie re-run, pas un cache hit silencieux.
    force: bool = True


class BatchRefreshItemResult(CamelModel):
    issue_id: int
    status: str  # "success" | "skipped" | "error"
    message: str | None = None
    run_id: int | None = None
    final: dict | None = None
    elapsed_ms: int = 0
    from_cache: bool = False


class BatchRefreshResponse(CamelModel):
    magazine_id: int
    total: int
    processed: int
    results: list[BatchRefreshItemResult]


@router.post("/reanalyze/{magazine_id}", response_model=ReanalyzeResponse)
async def reanalyze_magazine(
    magazine_id: int,
    body: ReanalyzeRequest,
    session: AsyncSession = Depends(get_session),
    config=Depends(get_config),
):
    """Trigger enrichment on a specific magazine's PDF.

    When ``issue_id`` is set, uses that issue's file. Otherwise
    picks the newest IssueFile linked to the magazine. If neither
    exists → run text-only (torrent name = magazine title).
    """
    mag = (
        await session.execute(select(Magazine).where(Magazine.id == magazine_id))
    ).scalars().first()
    if not mag:
        raise HTTPException(404, f"Magazine {magazine_id} not found")

    pdf_path: Path | None = None
    torrent_name = mag.title
    issue_id = body.issue_id
    if issue_id:
        f = (
            await session.execute(
                select(IssueFile).where(IssueFile.issue_id == issue_id)
            )
        ).scalars().first()
        if f and Path(f.path).exists():
            pdf_path = Path(f.path)
            torrent_name = f.original_filename or Path(f.path).name
    else:
        # Newest file for this magazine
        f = (
            await session.execute(
                select(IssueFile)
                .join(Issue, Issue.id == IssueFile.issue_id)
                .where(Issue.magazine_id == magazine_id)
                .order_by(desc(IssueFile.id))
                .limit(1)
            )
        ).scalars().first()
        if f and Path(f.path).exists():
            pdf_path = Path(f.path)
            torrent_name = f.original_filename or Path(f.path).name
            issue_id = f.issue_id

    from app.database import async_session_factory

    svc = AIEnrichmentService(config, async_session_factory)
    result = await svc.enrich(
        torrent_name=torrent_name,
        pdf_path=pdf_path,
        magazine_id=magazine_id,
        issue_id=issue_id,
        trigger="reanalyze",
        # User a explicitement cliqué le bouton — pas de cache silencieux.
        force=True,
    )

    # Optionally apply to the issue directly (bypass propose mode).
    if body.apply_result and result.final and issue_id:
        issue = (
            await session.execute(select(Issue).where(Issue.id == issue_id))
        ).scalars().first()
        if issue:
            # Reuse merge helper by faking a minimal parsed object.
            class _P:
                pass
            proxy = _P()
            for k in ("title", "number", "year", "month", "day"):
                setattr(proxy, k, getattr(issue, k if k != "title" else "number", None))
            proxy.title = mag.title
            proxy.number = issue.number
            proxy.year = issue.year
            proxy.month = issue.month
            proxy.day = issue.day
            merged = merge_ai_into_parsed(proxy, result.final, config.ai_enrichment_mode)
            issue.number = merged.number
            issue.year = merged.year
            issue.month = merged.month
            issue.day = merged.day
            await session.commit()

    return ReanalyzeResponse(
        run_id=result.run_id,
        applied_mode=result.applied_mode,
        final=result.final,
        steps=result.steps,
        total_elapsed_ms=result.total_elapsed_ms,
    )


@router.post(
    "/refresh-batch/{magazine_id}",
    response_model=BatchRefreshResponse,
)
async def refresh_batch(
    magazine_id: int,
    body: BatchRefreshRequest,
    session: AsyncSession = Depends(get_session),
    config=Depends(get_config),
):
    """Bulk refresh: classic metadata + AI text + AI vision, per issue.

    Sequential : chaque issue est traitée l'une après l'autre pour
    (a) respecter le switch model Ollama et (b) éviter de sursouscrire
    la GPU/CPU. Un burst de 20 issues avec vision peut prendre 20 min
    en CPU — le tracker Queue montre l'avancement.
    """
    mag = (
        await session.execute(select(Magazine).where(Magazine.id == magazine_id))
    ).scalars().first()
    if not mag:
        raise HTTPException(404, f"Magazine {magazine_id} not found")

    # Resolve target issues : explicit list wins, else all with a file.
    issues_q = select(Issue).where(Issue.magazine_id == magazine_id)
    if body.issue_ids:
        issues_q = issues_q.where(Issue.id.in_(body.issue_ids))
    issues = (await session.execute(issues_q)).scalars().all()

    # Preload each issue's file (may be None → issue has no downloaded PDF)
    file_map: dict[int, IssueFile] = {}
    if issues:
        files = (
            await session.execute(
                select(IssueFile).where(
                    IssueFile.issue_id.in_([i.id for i in issues])
                )
            )
        ).scalars().all()
        file_map = {f.issue_id: f for f in files}

    from app.database import async_session_factory

    results: list[BatchRefreshItemResult] = []
    processed = 0

    # 1. Classic metadata refresh — one call per magazine, not per
    # issue. If the user asked for it, run once BEFORE the AI loop
    # so downstream fields (TMDB collections, ratings) benefit the
    # arbitration.
    if body.include_metadata:
        try:
            from app.services.magazine_service import refresh_metadata

            await refresh_metadata(session, magazine_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Classic metadata refresh failed: %s", exc)

    # 2. Per-issue AI enrichment loop.
    if body.include_ai_text or body.include_ai_vision:
        # Toggle vision off in the runtime config for this batch when
        # the user unchecked it — the service reads
        # `ai_enrichment_vision_pages`; empty list disables vision.
        original_pages = config.ai_enrichment_vision_pages
        if not body.include_ai_vision:
            config.ai_enrichment_vision_pages = []

        try:
            svc = AIEnrichmentService(config, async_session_factory)
            for issue in issues:
                f = file_map.get(issue.id)
                if not f or not Path(f.path).exists():
                    results.append(BatchRefreshItemResult(
                        issue_id=issue.id,
                        status="skipped",
                        message="issue file missing on disk",
                    ))
                    continue
                # AI text only mode = torrent name = the file name.
                # AI vision needs the PDF path — only pass it when
                # `include_ai_vision` is True.
                pdf = Path(f.path) if body.include_ai_vision else None
                torrent_name = f.original_filename or Path(f.path).name
                try:
                    res = await svc.enrich(
                        torrent_name=torrent_name,
                        pdf_path=pdf,
                        magazine_id=magazine_id,
                        issue_id=issue.id,
                        trigger="reanalyze",
                        force=body.force,
                    )
                    # Apply the result to the issue if requested and
                    # something was extracted.
                    if body.apply_result and res.final:
                        for k_ai, k_iss in (
                            ("issue_number", "number"),
                            ("year", "year"),
                            ("month", "month"),
                            ("day", "day"),
                        ):
                            v = res.final.get(k_ai)
                            if v is not None:
                                setattr(issue, k_iss, v)
                    processed += 1
                    results.append(BatchRefreshItemResult(
                        issue_id=issue.id,
                        status="success",
                        run_id=res.run_id,
                        final=res.final,
                        elapsed_ms=res.total_elapsed_ms,
                        from_cache=(res.applied_mode == "cache_hit"),
                    ))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Batch enrich failed for issue %s: %s", issue.id, exc
                    )
                    results.append(BatchRefreshItemResult(
                        issue_id=issue.id,
                        status="error",
                        message=str(exc),
                    ))
            await session.commit()
        finally:
            config.ai_enrichment_vision_pages = original_pages
    else:
        # metadata-only batch : count as processed to give the UI a
        # meaningful summary.
        for issue in issues:
            results.append(BatchRefreshItemResult(
                issue_id=issue.id,
                status="success",
                message="metadata refresh only (no AI)",
            ))
            processed += 1

    return BatchRefreshResponse(
        magazine_id=magazine_id,
        total=len(issues),
        processed=processed,
        results=results,
    )


# ---------------------------------------------------------------------------
# Run history + detail
# ---------------------------------------------------------------------------


class EnrichmentRunResource(CamelModel):
    id: int
    magazine_id: int | None
    issue_id: int | None
    trigger: str
    status: str
    applied_mode: str
    steps: list[dict]
    final: dict
    error_message: str | None
    started_at: str
    completed_at: str | None
    total_elapsed_ms: int


@router.get("/runs/enrichment", response_model=list[EnrichmentRunResource])
async def list_enrichment_runs(
    magazine_id: int | None = None,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
):
    q = select(AIEnrichmentRun).order_by(desc(AIEnrichmentRun.started_at)).limit(limit)
    if magazine_id is not None:
        q = q.where(AIEnrichmentRun.magazine_id == magazine_id)
    rows = (await session.execute(q)).scalars().all()
    return [
        EnrichmentRunResource(
            id=r.id,
            magazine_id=r.magazine_id,
            issue_id=r.issue_id,
            trigger=r.trigger,
            status=r.status,
            applied_mode=r.applied_mode,
            steps=json.loads(r.steps_json or "[]"),
            final=json.loads(r.final_json or "{}"),
            error_message=r.error_message,
            started_at=r.started_at.isoformat() if r.started_at else "",
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            total_elapsed_ms=r.total_elapsed_ms,
        )
        for r in rows
    ]


class RankerRunResource(CamelModel):
    id: int
    magazine_id: int | None
    pattern_id: int | None
    status: str
    applied_mode: str
    model_used: str
    candidates: list[dict]
    batches: list[dict]
    final: dict
    scorer_top_index: int | None
    ai_picked_index: int | None
    confidence: float | None
    reason: str | None
    started_at: str
    completed_at: str | None
    total_elapsed_ms: int


@router.get("/runs/ranker", response_model=list[RankerRunResource])
async def list_ranker_runs(
    magazine_id: int | None = None,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
):
    q = select(AIRankerRun).order_by(desc(AIRankerRun.started_at)).limit(limit)
    if magazine_id is not None:
        q = q.where(AIRankerRun.magazine_id == magazine_id)
    rows = (await session.execute(q)).scalars().all()
    return [
        RankerRunResource(
            id=r.id,
            magazine_id=r.magazine_id,
            pattern_id=r.pattern_id,
            status=r.status,
            applied_mode=r.applied_mode,
            model_used=r.model_used,
            candidates=json.loads(r.candidates_json or "[]"),
            batches=json.loads(r.batches_json or "[]"),
            final=json.loads(r.final_json or "{}"),
            scorer_top_index=r.scorer_top_index,
            ai_picked_index=r.ai_picked_index,
            confidence=r.confidence,
            reason=r.reason,
            started_at=r.started_at.isoformat() if r.started_at else "",
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            total_elapsed_ms=r.total_elapsed_ms,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Proposals (propose mode)
# ---------------------------------------------------------------------------


class ProposalResource(CamelModel):
    id: int
    magazine_id: int | None
    issue_id: int | None
    run_id: int
    proposed: dict
    status: str
    created_at: str
    reviewed_at: str | None


@router.get("/proposals", response_model=list[ProposalResource])
async def list_proposals(
    magazine_id: int | None = None,
    status: str = "pending",
    session: AsyncSession = Depends(get_session),
):
    q = select(AIEnrichmentProposal).where(AIEnrichmentProposal.status == status)
    if magazine_id is not None:
        q = q.where(AIEnrichmentProposal.magazine_id == magazine_id)
    rows = (await session.execute(q)).scalars().all()
    out: list[ProposalResource] = []
    for r in rows:
        try:
            proposed = json.loads(r.proposed_json)
        except Exception:  # noqa: BLE001
            proposed = {"_raw": r.proposed_json}
        out.append(ProposalResource(
            id=r.id,
            magazine_id=r.magazine_id,
            issue_id=r.issue_id,
            run_id=r.run_id,
            proposed=proposed,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else "",
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
        ))
    return out


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Apply the proposed metadata to the linked issue, mark accepted."""
    from datetime import datetime

    prop = (
        await session.execute(
            select(AIEnrichmentProposal).where(AIEnrichmentProposal.id == proposal_id)
        )
    ).scalars().first()
    if not prop or prop.status != "pending":
        raise HTTPException(404, "Proposal not found or already reviewed")

    try:
        data = json.loads(prop.proposed_json)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Malformed proposal JSON: {exc}") from exc

    if prop.issue_id:
        issue = (
            await session.execute(select(Issue).where(Issue.id == prop.issue_id))
        ).scalars().first()
        if issue:
            for k_ai, k_issue in [
                ("issue_number", "number"),
                ("year", "year"),
                ("month", "month"),
                ("day", "day"),
            ]:
                v = data.get(k_ai)
                if v is not None:
                    setattr(issue, k_issue, v)
    prop.status = "accepted"
    prop.reviewed_at = datetime.utcnow()
    await session.commit()
    return {"status": "ok"}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: int,
    session: AsyncSession = Depends(get_session),
):
    from datetime import datetime

    prop = (
        await session.execute(
            select(AIEnrichmentProposal).where(AIEnrichmentProposal.id == proposal_id)
        )
    ).scalars().first()
    if not prop or prop.status != "pending":
        raise HTTPException(404, "Proposal not found or already reviewed")
    prop.status = "rejected"
    prop.reviewed_at = datetime.utcnow()
    await session.commit()
    return {"status": "ok"}
