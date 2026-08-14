"""AI-related endpoints — settings, Ollama probe, re-analyze, history detail."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
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
    enrichment_vision_crop: str  # full | top | bottom | top_bottom
    python_ocr_enabled: bool
    python_ocr_engine: str  # tesseract | rapidocr | easyocr
    text_model: str
    vision_model: str
    # Optional per-step overrides. Null = fall back to text_model.
    torrent_model: str | None = None
    arbiter_model: str | None = None
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
    enrichment_vision_crop: str | None = None
    python_ocr_enabled: bool | None = None
    python_ocr_engine: str | None = None
    text_model: str | None = None
    vision_model: str | None = None
    torrent_model: str | None = None
    arbiter_model: str | None = None
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
        enrichment_vision_crop=config.ai_enrichment_vision_crop,
        python_ocr_enabled=config.ai_python_ocr_enabled,
        python_ocr_engine=config.ai_python_ocr_engine,
        text_model=config.ai_text_model,
        vision_model=config.ai_vision_model,
        torrent_model=config.ai_torrent_model,
        arbiter_model=config.ai_arbiter_model,
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
    valid_pyocr_engines = {"tesseract", "rapidocr", "easyocr"}

    if body.enrichment_mode is not None and body.enrichment_mode not in valid_enrich_modes:
        raise HTTPException(400, f"Invalid enrichment mode; must be {valid_enrich_modes}")
    if body.python_ocr_engine is not None and body.python_ocr_engine not in valid_pyocr_engines:
        raise HTTPException(400, f"Invalid python OCR engine; must be {valid_pyocr_engines}")
    if body.ranker_mode is not None and body.ranker_mode not in valid_ranker_modes:
        raise HTTPException(400, f"Invalid ranker mode; must be {valid_ranker_modes}")

    fields_map = {
        "ollama_url": "ai_ollama_url",
        "ollama_timeout_s": "ai_ollama_timeout_s",
        "enrichment_enabled": "ai_enrichment_enabled",
        "enrichment_mode": "ai_enrichment_mode",
        "enrichment_vision_pages": "ai_enrichment_vision_pages",
        "enrichment_vision_crop": "ai_enrichment_vision_crop",
        "python_ocr_enabled": "ai_python_ocr_enabled",
        "python_ocr_engine": "ai_python_ocr_engine",
        "text_model": "ai_text_model",
        "vision_model": "ai_vision_model",
        "torrent_model": "ai_torrent_model",
        "arbiter_model": "ai_arbiter_model",
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


_OLLAMA_PROBE_CACHE: dict[str, tuple[float, OllamaModelsResource]] = {}
_OLLAMA_PROBE_TTL_S = 30.0


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

    Cache TTL 30 s pour ne pas re-tapper Ollama (remote, network ~500ms)
    à chaque render / focus de la page Settings.
    """
    import time as _t

    target = url or config.ai_ollama_url
    cached = _OLLAMA_PROBE_CACHE.get(target)
    if cached and (_t.monotonic() - cached[0]) < _OLLAMA_PROBE_TTL_S:
        return cached[1]
    adapter = OllamaAdapter(target, timeout_s=10)
    try:
        models = await adapter.list_models()
        result = OllamaModelsResource(
            reachable=True, url=adapter.url, models=models
        )
        _OLLAMA_PROBE_CACHE[target] = (_t.monotonic(), result)
        return result
    except Exception as exc:  # noqa: BLE001
        return OllamaModelsResource(
            reachable=False, url=adapter.url, models=[], error=str(exc)
        )


# ---------------------------------------------------------------------------
# Python OCR engines probe — tells the UI which of the 3 engines are
# actually importable/usable on this machine, so the dropdown greys
# out the ones missing (avoids saving a broken config).
# ---------------------------------------------------------------------------


class PythonOCRProbeEntry(CamelModel):
    engine: str
    available: bool
    error: str | None = None


@router.get(
    "/python-ocr/engines",
    response_model=list[PythonOCRProbeEntry],
)
async def probe_python_ocr_engines():
    """Return per-engine availability. Never raises."""
    from app.services.python_ocr_service import probe_available
    data = probe_available()
    return [
        PythonOCRProbeEntry(engine=name, available=info["available"], error=info.get("error"))
        for name, info in data.items()
    ]


class PipelineStepDoc(CamelModel):
    name: str
    label: str
    description: str
    kind: str
    inputs: list[str]
    outputs: list[str]
    optional: bool
    fan_out: bool


@router.get(
    "/pipeline/steps",
    response_model=list[PipelineStepDoc],
)
async def list_pipeline_steps():
    """Documentation ordonnée des étapes du pipeline metadata.

    Utilisé par le frontend (Settings/AI + History) pour afficher
    un diagramme du flow et rappeler les inputs/outputs de chaque
    step. Modifier cette liste : voir ``pipeline_registry.py``.
    """
    from app.services.pipeline_registry import as_dicts
    return as_dicts()


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
    # Toggles fins par étape du pipeline metadata. ``None`` = fallback
    # cohérent : True quand la source parente (ai_text/ai_vision) est
    # activée, False sinon. Le arbiter n'a de sens que si au moins une
    # source IA a tourné — le service décide en interne. Ces flags
    # laissent l'opérateur zapper une étape spécifique (ex. skip vision
    # LLM pour ne garder que python_ocr sur un magazine à bandeau
    # étroit qui pourrit systématiquement minicpm-v).
    include_python_ocr: bool | None = None
    include_ai_arbiter: bool | None = None
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
    """Kick-off response — le batch réel tourne en background.

    Le user suit l'avancement dans la Queue : chaque issue ajoutée
    crée un item ``ImportActivity`` avec les steps IA + import
    poussés au fil de l'eau.
    """

    magazine_id: int
    total: int  # nombre d'issues sélectionnées + éligibles
    queued: int  # activities créées dans le tracker Queue
    background: bool = True  # signale au front que c'est fire-and-forget
    skipped_no_file: list[int] = []  # issues ignorées faute de PDF


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
    from app.services import activity_service as _asvc_re

    _re_activity: int | None = None
    try:
        _re_activity = await _asvc_re.create(
            kind="ai_refresh",
            title=f"Analyse IA · {mag.title}"
                + (f" #{issue_id}" if issue_id else ""),
            subtitle="Re-analyse manuelle (bypass cache)",
            magazine_id=magazine_id,
            issue_id=issue_id,
            payload={"torrent_name": torrent_name},
        )
    except Exception:
        pass

    def _reanalyze_cb(stage: str, detail: str) -> None:
        if _re_activity is None:
            return
        try:
            import asyncio as _aio
            _aio.get_running_loop().create_task(
                _asvc_re.push_step(
                    _re_activity,
                    {"step": stage, "label": stage, "hint": detail},
                )
            )
        except Exception:
            pass

    svc = AIEnrichmentService(config, async_session_factory)
    try:
        result = await svc.enrich(
            torrent_name=torrent_name,
            pdf_path=pdf_path,
            magazine_id=magazine_id,
            issue_id=issue_id,
            trigger="reanalyze",
            progress_cb=_reanalyze_cb,
            # User a explicitement cliqué le bouton — pas de cache silencieux.
            force=True,
        )
    except Exception as e:
        if _re_activity is not None:
            try:
                await _asvc_re.mark_error(_re_activity, str(e))
            except Exception:
                pass
        raise
    if _re_activity is not None:
        try:
            await _asvc_re.mark_done(
                _re_activity,
                hint=f"✓ {result.total_elapsed_ms / 1000:.1f}s"
                    if result.applied_mode != "cache_hit"
                    else f"⚡ cache — {result.total_elapsed_ms}ms",
            )
        except Exception:
            pass

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
            # Conflict guard : cf. _run_batch_background — un forecast
            # peut déjà porter le numéro cible, on le supprime pour
            # laisser la place à cet import « authoritative ».
            new_number = merged.number
            if new_number is not None and issue.number != new_number:
                from sqlalchemy.orm import selectinload
                conflict = (
                    await session.execute(
                        select(Issue)
                        .options(selectinload(Issue.file))
                        .where(
                            Issue.magazine_id == issue.magazine_id,
                            Issue.number == new_number,
                            Issue.id != issue.id,
                        )
                    )
                ).scalars().first()
                if conflict and conflict.file is None:
                    logger.info(
                        "Reanalyze apply: dropping forecast issue %d (#%s) "
                        "to free the number for issue %d",
                        conflict.id, new_number, issue.id,
                    )
                    await session.delete(conflict)
                    await session.flush()
                elif conflict is not None:
                    logger.warning(
                        "Reanalyze apply: issue %d wants #%s but issue %d "
                        "has it with a file → keeping current",
                        issue.id, new_number, conflict.id,
                    )
                    new_number = None
            if new_number is not None:
                issue.number = new_number
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


# ---------------------------------------------------------------------------
# Custom crop rectangle — l'user le définit visuellement dans le modal
# Refresh IA, on le persiste sur Magazine, et le pipeline vision l'utilise.
# ---------------------------------------------------------------------------


class CropZone(CamelModel):
    """One custom zone drawn by the operator on the cover.

    Coords are ratios 0..1 of the full page. ``rotation`` is a
    clockwise angle in {0, 90, 180, 270} that will be applied to
    the rendered crop BEFORE being sent to the vision model —
    useful for narrow vertical strips (Paris Match tarif) whose
    text is printed at 90°.

    ``label`` : free-form UI hint ("Masthead haut", "Tarif vertical").

    ``tag`` : vocabulaire STRUCTURÉ qui pilote le prompt vision
    envoyé pour cette zone. Vocabulaire fixe :
      - ``number`` : cherche uniquement le N° d'édition
      - ``date``   : cherche la date de publication
      - ``title``  : titre principal
      - ``subtitle``: sous-titre / accroche
      - ``price``  : prix + mentions tarif
      - ``publisher``: éditeur / mentions légales
      - ``all``    : OCR exhaustif (comportement historique)
      - ``custom`` : voir champ ``custom_tag``

    ``custom_tag`` : texte libre utilisé quand ``tag == "custom"``
    pour construire un prompt sur-mesure ("cherche le code-barre").
    """

    x: float
    y: float
    w: float
    h: float
    rotation: int = 0
    label: str | None = None
    tag: str = "all"
    custom_tag: str | None = None


class CropRectResponse(CamelModel):
    magazine_id: int
    zones: list[CropZone] = []


def _parse_stored_crop(raw: str | None) -> list[CropZone]:
    """Parse the ai_crop_rect DB blob, tolerant to legacy shapes.

    Old shape (single dict) -> promoted to a single-zone list.
    New shape (list of dicts) -> kept as-is (rotation/label optional).
    """
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return []
    if isinstance(data, dict):
        raw_zones = [data]
    elif isinstance(data, list):
        raw_zones = data
    else:
        return []
    out: list[CropZone] = []
    for z in raw_zones:
        if not isinstance(z, dict):
            continue
        try:
            out.append(CropZone(
                x=float(z["x"]),
                y=float(z["y"]),
                w=float(z["w"]),
                h=float(z["h"]),
                rotation=int(z.get("rotation") or 0) % 360,
                label=(z.get("label") or None),
                tag=(z.get("tag") or "all"),
                custom_tag=(z.get("custom_tag") or None),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return out


@router.get(
    "/magazine/{magazine_id}/crop",
    response_model=CropRectResponse,
)
async def get_magazine_crop(
    magazine_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Renvoie la liste des zones custom du magazine (peut etre vide)."""
    mag = (
        await session.execute(select(Magazine).where(Magazine.id == magazine_id))
    ).scalars().first()
    if not mag:
        raise HTTPException(404, "Magazine not found")
    return CropRectResponse(
        magazine_id=magazine_id,
        zones=_parse_stored_crop(mag.ai_crop_rect),
    )


class CropUpdateRequest(CamelModel):
    """Body for PUT /crop -- always a list (empty = clear all)."""

    zones: list[CropZone] = []


@router.put(
    "/magazine/{magazine_id}/crop",
    response_model=CropRectResponse,
)
async def set_magazine_crop(
    magazine_id: int,
    body: CropUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Remplace intégralement la liste des zones custom.

    Envoyer ``{"zones": []}`` efface le crop custom (fallback global).
    """
    mag = (
        await session.execute(select(Magazine).where(Magazine.id == magazine_id))
    ).scalars().first()
    if not mag:
        raise HTTPException(404, "Magazine not found")
    if not body.zones:
        mag.ai_crop_rect = None
    else:
        valid_tags = {
            "number", "date", "title", "subtitle",
            "price", "publisher", "issn", "all", "custom",
        }
        clamped: list[dict] = []
        for z in body.zones:
            x = max(0.0, min(1.0, z.x))
            y = max(0.0, min(1.0, z.y))
            w = max(0.01, min(1.0 - x, z.w))
            h = max(0.01, min(1.0 - y, z.h))
            rot = int(z.rotation or 0) % 360
            if rot not in (0, 90, 180, 270):
                rot = 0
            tag = z.tag if z.tag in valid_tags else "all"
            entry: dict = {"x": x, "y": y, "w": w, "h": h, "rotation": rot, "tag": tag}
            if z.label:
                entry["label"] = z.label.strip()[:40]
            if tag == "custom" and z.custom_tag:
                entry["custom_tag"] = z.custom_tag.strip()[:120]
            clamped.append(entry)
        mag.ai_crop_rect = json.dumps(clamped)
    await session.commit()
    return await get_magazine_crop(magazine_id, session)


@router.get("/magazine/{magazine_id}/issue-cover-preview")
async def issue_cover_preview(
    magazine_id: int,
    issue_id: int = Query(..., alias="issueId"),
    session: AsyncSession = Depends(get_session),
):
    """Rend la page 1 d'une issue SPÉCIFIQUE en PNG.

    Utilisé par le crop editor pour parcourir les issues disponibles
    et valider les zones sur plusieurs couvertures. 404 si l'issue
    n'a pas de fichier ou n'appartient pas au magazine.
    """
    from fastapi.responses import Response

    row = (
        await session.execute(
            select(IssueFile)
            .join(Issue, Issue.id == IssueFile.issue_id)
            .where(
                Issue.magazine_id == magazine_id,
                Issue.id == issue_id,
            )
            .limit(1)
        )
    ).scalars().first()
    if not row or not Path(row.path).exists():
        raise HTTPException(404, "No PDF for this issue")
    from app.services.ai_enrichment_service import _render_page_pngs
    try:
        rendered = _render_page_pngs(
            Path(row.path), 1, dpi=120, crop_mode="full",
        )
        png = rendered[0][1]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Render failed: {exc}") from exc
    return Response(content=png, media_type="image/png")


@router.get("/magazine/{magazine_id}/cover-preview")
async def magazine_cover_preview(
    magazine_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Rend la page 1 d'une issue avec fichier en PNG pour l'UI crop.

    Sert l'image telle quelle (Content-Type: image/png) au lieu de
    JSON — le front l'affiche dans un ``<img>``. On prend le plus
    récent IssueFile du magazine ; si aucun, 404.

    DPI 120 : compromis nettéte/poids pour un affichage web (~500-
    800 KB), pas l'inférence — cette image sert UNIQUEMENT à laisser
    l'user dessiner le rect à la souris.
    """
    from fastapi.responses import Response

    mag = (
        await session.execute(select(Magazine).where(Magazine.id == magazine_id))
    ).scalars().first()
    if not mag:
        raise HTTPException(404, "Magazine not found")
    f = (
        await session.execute(
            select(IssueFile)
            .join(Issue, Issue.id == IssueFile.issue_id)
            .where(Issue.magazine_id == magazine_id)
            .order_by(desc(IssueFile.id))
            .limit(1)
        )
    ).scalars().first()
    if not f or not Path(f.path).exists():
        raise HTTPException(404, "No PDF available for this magazine")
    from app.services.ai_enrichment_service import _render_page_pngs
    try:
        rendered = _render_page_pngs(
            Path(f.path), 1, dpi=120, crop_mode="full",
        )
        png = rendered[0][1]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Render failed: {exc}") from exc
    return Response(content=png, media_type="image/png")


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
    """Kick-off a background bulk enrichment.

    Returns immediately with the number of activities queued. Actual
    per-issue work runs in a detached asyncio task ; live progress is
    visible via /api/v1/queue (chaque issue = un ImportActivity avec
    ses steps IA + import).

    Sequential across issues (respecte le switch model Ollama). Total
    duration can easily hit 15-30 min pour un batch vision de 20 issues
    en CPU — mais c'est non bloquant, l'UI peut faire autre chose.
    """
    mag = (
        await session.execute(select(Magazine).where(Magazine.id == magazine_id))
    ).scalars().first()
    if not mag:
        raise HTTPException(404, f"Magazine {magazine_id} not found")

    # Resolve target issues + files SYNCHRONOUSLY (avant de céder le
    # session) — ensuite on lâche la session pour éviter le lock DB
    # pendant la boucle background.
    issues_q = select(Issue).where(Issue.magazine_id == magazine_id)
    if body.issue_ids:
        issues_q = issues_q.where(Issue.id.in_(body.issue_ids))
    issues = (await session.execute(issues_q)).scalars().all()

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

    # Extract les tuples utilisables plain-python (paths, ids) —
    # évite de garder des ORM objects hors session.
    magazine_title = mag.title
    work_items: list[tuple[int, str, str | None]] = []  # (issue_id, torrent_name, pdf_path)
    skipped_no_file: list[int] = []
    for issue in issues:
        f = file_map.get(issue.id)
        needs_file = body.include_ai_vision
        if needs_file and (not f or not Path(f.path).exists()):
            skipped_no_file.append(issue.id)
            continue
        torrent_name = (
            f.original_filename or Path(f.path).name if f else f"{magazine_title}"
        )
        pdf_path = (
            str(f.path) if (f and body.include_ai_vision and Path(f.path).exists())
            else None
        )
        work_items.append((issue.id, torrent_name, pdf_path))

    # Pré-enregistre les activities Queue MAINTENANT (avant de partir
    # en background) — l'user voit tout de suite les items « en attente
    # d'import » avec le bon nom de fichier.
    from app.services.import_activity_tracker import tracker as _act
    for issue_id, torrent_name, _ in work_items:
        _act.register(
            activity_id=f"reanalyze:{magazine_id}:{issue_id}",
            file_name=torrent_name,
            magazine_id=magazine_id,
            issue_id=issue_id,
            magazine_title=magazine_title,
        )

    # 1. Metadata classique : synchronously OK, ça ne peut être qu'un
    # appel par magazine et ça termine en 5-30s (Google Books, IA).
    # Ça permet aux prochains AI runs de bénéficier des metadata frais.
    if body.include_metadata:
        try:
            from app.services.magazine_service import refresh_metadata
            await refresh_metadata(session, magazine_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Classic metadata refresh failed: %s", exc)

    # 2. Lancer la boucle IA en background — asyncio.create_task pour
    # que le HTTP response part IMMÉDIATEMENT. La task tourne sur
    # l'event loop du process principal, avec sa propre session_factory.
    if work_items and (
        body.include_ai_text
        or body.include_ai_vision
        or body.include_python_ocr
    ):
        import asyncio

        # Snapshot des settings AI (l'user pourrait changer entre le
        # kick-off et la fin — on lock les valeurs pour ce batch).
        vision_pages_snap = (
            config.ai_enrichment_vision_pages if body.include_ai_vision else []
        )
        # Fallback logic pour python_ocr / arbiter : par défaut ON
        # si la source parente (vision) l'est aussi.
        python_ocr_enabled = (
            body.include_python_ocr
            if body.include_python_ocr is not None
            else body.include_ai_vision
        )
        arbiter_enabled = (
            body.include_ai_arbiter
            if body.include_ai_arbiter is not None
            else (body.include_ai_vision or body.include_python_ocr is not False)
        )

        asyncio.create_task(
            _run_batch_background(
                magazine_id=magazine_id,
                work_items=work_items,
                vision_pages=vision_pages_snap,
                python_ocr_enabled=python_ocr_enabled,
                arbiter_enabled=arbiter_enabled,
                torrent_ai_enabled=body.include_ai_text,
                apply_result=body.apply_result,
                force=body.force,
                config=config,
            )
        )

    return BatchRefreshResponse(
        magazine_id=magazine_id,
        total=len(issues),
        queued=len(work_items),
        background=True,
        skipped_no_file=skipped_no_file,
    )


async def _run_batch_background(
    *,
    magazine_id: int,
    work_items: list[tuple[int, str, str | None]],
    vision_pages: list[int],
    python_ocr_enabled: bool,
    arbiter_enabled: bool,
    apply_result: bool,
    force: bool,
    config,
    torrent_ai_enabled: bool = True,
) -> None:
    """Boucle sequential des enrichissements — tourne détaché.

    Chaque issue :
    1. Push steps dans le tracker Queue via progress_cb
    2. Écrit optionnellement les fields extraits sur l'issue en DB
    3. Marque l'activity comme success/error dans le tracker

    Une exception sur une issue n'arrête pas le batch — on passe à la
    suivante et on log.
    """
    from app.database import async_session_factory
    from app.services import activity_service as _asvc
    from app.services.ai_enrichment_service import (
        AIEnrichmentService,
        merge_ai_into_parsed,
    )
    from app.services.import_activity_tracker import tracker as _act

    # Activité batch-level : le user voit UNE ligne dans Activity qui
    # trace la progression global du refresh. Chaque issue continue
    # d'avoir sa propre activity via _act (import_activity_tracker).
    batch_activity_id: int | None = None
    try:
        from app.models.magazine import Magazine as _Mag
        async with async_session_factory() as _s:
            _m = (await _s.execute(
                select(_Mag).where(_Mag.id == magazine_id)
            )).scalar_one_or_none()
        _mag_title = _m.title if _m else f"magazine #{magazine_id}"
        batch_activity_id = await _asvc.create(
            kind="ai_refresh",
            title=f"Refresh IA · {_mag_title}",
            subtitle=f"{len(work_items)} issue(s)",
            magazine_id=magazine_id,
            payload={
                "issue_count": len(work_items),
                "python_ocr": python_ocr_enabled,
                "arbiter": arbiter_enabled,
                "torrent_ai": torrent_ai_enabled,
                "vision_pages": vision_pages,
                "apply": apply_result,
                "force": force,
            },
        )
    except Exception:
        logger.debug("Activity mirror (ai_refresh batch) failed", exc_info=True)

    # Override runtime : ai_enrichment_vision_pages contrôle la vision,
    # ai_python_ocr_enabled contrôle l'OCR python, ai_arbiter_model
    # (à travers effective_arbiter_model) contrôle l'arbiter. On snap
    # + restore les 3 pour ce batch.
    original_pages = config.ai_enrichment_vision_pages
    original_pyocr = getattr(config, "ai_python_ocr_enabled", True)
    original_arbiter_model = getattr(config, "ai_arbiter_model", None)
    original_torrent_model = getattr(config, "ai_torrent_model", None)
    original_text_model = getattr(config, "ai_text_model", None)
    config.ai_enrichment_vision_pages = vision_pages
    config.ai_python_ocr_enabled = python_ocr_enabled
    if not arbiter_enabled:
        # Force le pipeline à ne pas avoir de modèle arbitre dispo →
        # fallback deterministic-python natif.
        config.ai_arbiter_model = "__disabled__"
    if not torrent_ai_enabled:
        # Skip l'analyse LLM du nom torrent — le pipeline gère le
        # modèle absent en sautant proprement l'étape.
        config.ai_torrent_model = "__disabled__"
        config.ai_text_model = "__disabled__"

    try:
        svc = AIEnrichmentService(config, async_session_factory)

        _completed = 0
        _errors = 0
        for _idx, (issue_id, torrent_name, pdf_path_str) in enumerate(work_items, start=1):
            activity_id = f"reanalyze:{magazine_id}:{issue_id}"
            if batch_activity_id is not None:
                try:
                    await _asvc.push_step(
                        batch_activity_id,
                        {
                            "step": "issue",
                            "label": f"Issue {_idx}/{len(work_items)}",
                            "hint": torrent_name[:120],
                            "issue_id": issue_id,
                        },
                    )
                    await _asvc.update_progress(
                        batch_activity_id,
                        (_idx - 1) * 100 / max(1, len(work_items)),
                    )
                except Exception:
                    pass

            def _cb(stage: str, detail: str, aid: str = activity_id) -> None:
                _stage_map = {
                    "text": "ai_text",
                    "vision": "ai_vision",
                    "switch": (
                        "ai_switch_vision" if "vision" in detail.lower()
                        else "ai_switch_text"
                    ),
                    "arbiter": "ai_arbiter",
                    "skip": "ai_skipped",
                    "cache": "ai_skipped",
                }
                _act.push_step(
                    aid, _stage_map.get(stage, f"ai_{stage}"), hint=detail
                )

            try:
                pdf = Path(pdf_path_str) if pdf_path_str else None
                res = await svc.enrich(
                    torrent_name=torrent_name,
                    pdf_path=pdf,
                    magazine_id=magazine_id,
                    issue_id=issue_id,
                    trigger="reanalyze",
                    progress_cb=_cb,
                    force=force,
                )

                # Apply to DB if requested — session dédiée pour éviter
                # les conflits avec le service AI qui a la sienne.
                if apply_result and res.final:
                    try:
                        async with async_session_factory() as sess:
                            iss = (
                                await sess.execute(
                                    select(Issue).where(Issue.id == issue_id)
                                )
                            ).scalars().first()
                            if iss:
                                new_number = res.final.get("issue_number")
                                # Conflit potentiel : un forecast (ou autre
                                # issue vide) porte déjà ce numéro dans le
                                # magazine. Cas typique après enrichissement
                                # IA qui trouve « #4033 » alors qu'un forecast
                                # #4033 auto-généré existe déjà. On supprime
                                # le forecast conflict pour laisser la place.
                                if (
                                    new_number is not None
                                    and iss.number != new_number
                                ):
                                    conflict = (
                                        await sess.execute(
                                            select(Issue).where(
                                                Issue.magazine_id == iss.magazine_id,
                                                Issue.number == new_number,
                                                Issue.id != iss.id,
                                            )
                                        )
                                    ).scalars().first()
                                    if conflict is not None:
                                        from sqlalchemy.orm import selectinload
                                        # Recharge avec le fichier pour
                                        # décider quoi faire
                                        conflict = (
                                            await sess.execute(
                                                select(Issue)
                                                .options(selectinload(Issue.file))
                                                .where(Issue.id == conflict.id)
                                            )
                                        ).scalars().first()
                                        if conflict and conflict.file is None:
                                            # Vide → on peut le sacrifier
                                            logger.info(
                                                "Enrichment apply: dropping "
                                                "forecast issue %d (#%s) to free "
                                                "the number for issue %d",
                                                conflict.id, new_number, iss.id,
                                            )
                                            await sess.delete(conflict)
                                            await sess.flush()
                                        else:
                                            # Conflit avec un vrai fichier —
                                            # on ne touche pas au number pour
                                            # ne pas casser l'autre issue.
                                            logger.warning(
                                                "Enrichment apply: issue %d "
                                                "wants #%s but issue %d has it "
                                                "with a file → keeping current",
                                                iss.id, new_number,
                                                conflict.id if conflict else "?",
                                            )
                                            new_number = None
                                # Update fields (year/month/day/issn, puis number)
                                for k_ai, k_iss in (
                                    ("year", "year"),
                                    ("month", "month"),
                                    ("day", "day"),
                                    ("issn", "issn"),
                                ):
                                    v = res.final.get(k_ai)
                                    if v is not None:
                                        setattr(iss, k_iss, v)
                                if new_number is not None:
                                    iss.number = new_number
                                await sess.commit()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Apply enrichment to issue %s failed: %s",
                            issue_id, exc,
                        )

                _act.mark_done(
                    activity_id,
                    hint=(
                        f"⚡ cache — {res.total_elapsed_ms}ms"
                        if res.applied_mode == "cache_hit"
                        else f"✓ {res.total_elapsed_ms / 1000:.1f}s"
                    ),
                )
                _completed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Batch enrich failed for issue %s: %s",
                    issue_id, exc, exc_info=True,
                )
                _act.mark_error(activity_id, str(exc))
                _errors += 1
                # continue avec l'issue suivante — un enrichissement raté
                # n'annule pas le batch entier.

    finally:
        config.ai_enrichment_vision_pages = original_pages
        config.ai_python_ocr_enabled = original_pyocr
        config.ai_arbiter_model = original_arbiter_model
        config.ai_torrent_model = original_torrent_model
        config.ai_text_model = original_text_model
        if batch_activity_id is not None:
            try:
                await _asvc.mark_done(
                    batch_activity_id,
                    hint=(
                        f"{_completed}/{len(work_items)} OK · {_errors} erreur(s)"
                    ),
                )
            except Exception:
                logger.debug("Activity finalize (ai_refresh batch) failed", exc_info=True)


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
