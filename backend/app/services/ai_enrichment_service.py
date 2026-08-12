"""AI metadata enrichment pipeline for magazines.

Sequential pipeline (per the user requirement — no parallelism so
the queue shows a clean step-by-step trace) :

    0. cache check              (skip if hit)
    1. text LLM                 (torrent name → JSON)
    2. switch model             (unload text, load vision)
    3. vision LLM × N pages     (cover, back, ...)
    4. switch model             (unload vision, load arbiter = text)
    5. arbiter LLM              (merge torrent + vision → final JSON)
    6. write result             (mode-dependent : replace/complete/propose)

Each stage emits a progress event via ``progress_cb(stage, detail)``
so the caller (import service, reanalyze endpoint) can push it to
the queue UI.

Fallback rule : any Ollama step that fails (model missing, network
error, invalid JSON output) is logged and the pipeline skips
gracefully to the caller's native parser. It NEVER raises out —
enrichment is optional value-add, not a blocker for import.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.services.ai_ollama_adapter import (
    OllamaAdapter,
    OllamaError,
    encode_image_file,
)

logger = logging.getLogger(__name__)


ProgressCb = Callable[[str, str], None]


@dataclass
class EnrichmentResult:
    """Return value of ``enrich()`` — safe to consume regardless of mode.

    ``final`` is the merged fields (may be empty dict if pipeline
    fell back). ``applied_mode`` describes what was actually done :
    ``remplace`` / ``complete`` / ``propose`` / ``skipped_fallback``.
    ``run_id`` is the id of the ``AIEnrichmentRun`` row created for
    this execution — the caller may link the row to its own job.
    """

    final: dict[str, Any]
    applied_mode: str
    run_id: int
    steps: list[dict[str, Any]] = field(default_factory=list)
    total_elapsed_ms: int = 0


def pdf_hash(pdf_path: Path | None) -> str:
    """SHA-256 of the PDF binary, or empty string when no file.

    Combined with magazine_id, this is the cache key. Any byte change
    in the file → cache miss → full re-run. Cheap on typical
    magazine sizes (~10-50 MB, sub-second on any SSD).
    """
    if pdf_path is None or not pdf_path.exists():
        return ""
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _render_page_png(pdf_path: Path, page_index_1based: int, dpi: int = 150) -> bytes:
    """Render a single PDF page to PNG bytes.

    ``page_index_1based`` : 1 = first page ; negative counts from the
    end (-1 = last). ``dpi`` : 150 is a fair balance for OCR — higher
    doesn't measurably help minicpm-v and slows the base64 upload.
    Raises IndexError when the page doesn't exist.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    try:
        n = doc.page_count
        if page_index_1based < 0:
            idx0 = n + page_index_1based  # -1 → n-1
        else:
            idx0 = page_index_1based - 1
        if idx0 < 0 or idx0 >= n:
            raise IndexError(
                f"Page {page_index_1based} out of range (PDF has {n} pages)"
            )
        page = doc.load_page(idx0)
        # DPI → zoom factor. Default 72 DPI in fitz.
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return pix.tobytes(output="png")
    finally:
        doc.close()


class AIEnrichmentService:
    """Owns the enrichment pipeline. Stateless between calls.

    ``config`` : app Config (holds ai_* fields).
    ``session_factory`` : callable returning a fresh AsyncSession
    context manager (used for cache lookup + run persistence). The
    caller is expected to pass an ``async_sessionmaker`` reference
    so this service doesn't depend on the request-scoped DB.
    """

    def __init__(self, config, session_factory) -> None:
        self._config = config
        self._session_factory = session_factory
        self._ollama = OllamaAdapter(
            url=config.ai_ollama_url, timeout_s=config.ai_ollama_timeout_s
        )

    async def enrich(
        self,
        torrent_name: str,
        pdf_path: Path | None,
        magazine_id: int | None,
        issue_id: int | None,
        trigger: str,
        progress_cb: ProgressCb | None = None,
    ) -> EnrichmentResult:
        """Run the full pipeline. Never raises — degrades to fallback.

        ``torrent_name`` : usually the source filename ; used verbatim
        by the text LLM prompt.
        ``pdf_path`` : local path to the imported PDF ; None → skip
        vision step entirely (text-only enrichment).
        ``trigger`` : "grab_auto" | "import_manual" | "reanalyze" —
        stored on the run for history filtering.
        ``progress_cb(stage, detail)`` : optional hook the caller
        wires to its queue progress step.
        """
        cfg = self._config
        cb = progress_cb or (lambda s, d: None)
        t0 = time.monotonic()

        pdfhash = pdf_hash(pdf_path)
        steps: list[dict[str, Any]] = []

        # --- 0. Cache check --------------------------------------
        cached = await self._lookup_cache(magazine_id, pdfhash)
        if cached is not None:
            cb("cache", "hit — utilisation du dernier résultat validé")
            return EnrichmentResult(
                final=cached["final"],
                applied_mode=cached["applied_mode"],
                run_id=cached["id"],
                steps=cached["steps"],
                total_elapsed_ms=cached["total_elapsed_ms"],
            )

        # --- Create the run row up-front so the UI can poll ------
        run_id = await self._create_run_row(
            magazine_id=magazine_id,
            issue_id=issue_id,
            trigger=trigger,
            pdf_hash=pdfhash,
        )

        # --- Guard 1 : Ollama reachable + models present ---------
        available = await self._ollama.list_models()
        if not available:
            cb("skip", "Ollama injoignable — fallback parser natif")
            return await self._finalize_skip(run_id, steps, t0, "ollama_unreachable")
        if cfg.ai_text_model not in available:
            cb("skip", f"Modèle texte '{cfg.ai_text_model}' absent — fallback")
            return await self._finalize_skip(run_id, steps, t0, "text_model_missing")

        # --- 1. Text LLM ----------------------------------------
        cb("text", f"Analyse nom torrent avec {cfg.ai_text_model}")
        text_result, text_step = await self._call_json(
            model=cfg.ai_text_model,
            prompt=(
                f"{cfg.ai_text_prompt}\n\n---\nNom de fichier : "
                f"{torrent_name}"
            ),
            step_name="text",
        )
        steps.append(text_step)

        # --- Guard 2 : vision available? ------------------------
        vision_outputs: list[dict[str, Any]] = []
        has_vision = (
            pdf_path is not None
            and cfg.ai_vision_model in available
            and cfg.ai_enrichment_vision_pages
        )
        if pdf_path is None:
            cb("skip", "Pas de PDF fourni — enrichissement texte seul")
        elif cfg.ai_vision_model not in available:
            cb("skip", f"Modèle vision '{cfg.ai_vision_model}' absent — texte seul")
        elif not cfg.ai_enrichment_vision_pages:
            cb("skip", "Aucune page vision configurée — texte seul")

        if has_vision:
            # --- 2. Switch : unload text, load vision ---------
            cb("switch", f"Chargement modèle vision {cfg.ai_vision_model}…")
            await self._ollama.unload_model(cfg.ai_text_model)

            pages = cfg.ai_enrichment_vision_pages or [1]
            for idx, page_num in enumerate(pages, 1):
                stage = f"vision {idx}/{len(pages)}"
                cb("vision", f"OCR page {page_num} ({idx}/{len(pages)})")
                try:
                    png_bytes = _render_page_png(pdf_path, page_num)
                except (IndexError, Exception) as exc:  # noqa: BLE001
                    logger.warning(
                        "Page %s render failed: %s", page_num, exc
                    )
                    steps.append({
                        "step": "vision",
                        "page": page_num,
                        "model": cfg.ai_vision_model,
                        "output": None,
                        "error": f"render_failed: {exc}",
                        "elapsed_ms": 0,
                    })
                    continue

                import base64
                img_b64 = base64.b64encode(png_bytes).decode("ascii")
                v_output, v_step = await self._call_json(
                    model=cfg.ai_vision_model,
                    prompt=cfg.ai_vision_prompt,
                    step_name="vision",
                    images_b64=[img_b64],
                    extra_step_fields={"page": page_num},
                )
                steps.append(v_step)
                if v_output is not None:
                    vision_outputs.append({"page": page_num, "data": v_output})

            # --- 4. Switch back to text model for arbiter -----
            cb("switch", f"Rechargement modèle arbitre {cfg.ai_text_model}…")
            await self._ollama.unload_model(cfg.ai_vision_model)

        # --- 5. Arbiter ------------------------------------------
        # Only call the arbiter when we have vision data to reconcile.
        # Text-only runs use the text output directly.
        if vision_outputs:
            cb("arbiter", f"Arbitrage avec {cfg.ai_text_model}")
            arb_prompt = (
                f"{cfg.ai_arbiter_prompt}\n\n---\n"
                f"Torrent : {json.dumps(text_result or {}, ensure_ascii=False)}\n"
                f"Vision : {json.dumps(vision_outputs, ensure_ascii=False)}"
            )
            arb_output, arb_step = await self._call_json(
                model=cfg.ai_text_model,
                prompt=arb_prompt,
                step_name="arbiter",
            )
            steps.append(arb_step)
            final = arb_output or text_result or {}
        else:
            final = text_result or {}

        # --- 6. Persist ------------------------------------------
        cb("done", f"{sum(1 for k, v in final.items() if v is not None)} champs extraits")
        elapsed = int((time.monotonic() - t0) * 1000)
        applied = cfg.ai_enrichment_mode
        await self._finalize_run(
            run_id=run_id,
            steps=steps,
            final=final,
            applied_mode=applied,
            elapsed_ms=elapsed,
            status="success",
        )
        return EnrichmentResult(
            final=final,
            applied_mode=applied,
            run_id=run_id,
            steps=steps,
            total_elapsed_ms=elapsed,
        )

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------

    async def _call_json(
        self,
        *,
        model: str,
        prompt: str,
        step_name: str,
        images_b64: list[str] | None = None,
        extra_step_fields: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Wrap an Ollama call with timing + step recording.

        Returns ``(output, step_record)``. On failure, ``output`` is
        None and ``step_record["error"]`` holds the message. Never
        raises — the pipeline must be able to continue with partial
        data.
        """
        t0 = time.monotonic()
        step: dict[str, Any] = {
            "step": step_name,
            "model": model,
            "output": None,
            "error": None,
            "elapsed_ms": 0,
        }
        if extra_step_fields:
            step.update(extra_step_fields)
        try:
            out = await self._ollama.generate_json(
                model=model,
                prompt=prompt,
                images_b64=images_b64,
            )
            step["output"] = out
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            return out, step
        except OllamaError as exc:
            step["error"] = str(exc)
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            logger.warning("AI step %s failed: %s", step_name, exc)
            return None, step

    async def _lookup_cache(
        self, magazine_id: int | None, pdfhash: str
    ) -> dict[str, Any] | None:
        """Return the newest successful run for this (magazine, pdf) or None.

        Cache is disabled when magazine_id is None (freshly parsed
        file, no magazine matched yet) — the run still writes to the
        journal for debug but subsequent identical runs won't skip.
        """
        if magazine_id is None:
            return None
        from sqlalchemy import select

        from app.models.ai_run import AIEnrichmentRun

        async with self._session_factory() as session:
            q = (
                select(AIEnrichmentRun)
                .where(
                    AIEnrichmentRun.magazine_id == magazine_id,
                    AIEnrichmentRun.pdf_hash == pdfhash,
                    AIEnrichmentRun.status == "success",
                )
                .order_by(AIEnrichmentRun.started_at.desc())
                .limit(1)
            )
            row = (await session.execute(q)).scalars().first()
            if not row:
                return None
            return {
                "id": row.id,
                "final": json.loads(row.final_json or "{}"),
                "applied_mode": row.applied_mode,
                "steps": json.loads(row.steps_json or "[]"),
                "total_elapsed_ms": row.total_elapsed_ms,
            }

    async def _create_run_row(
        self,
        *,
        magazine_id: int | None,
        issue_id: int | None,
        trigger: str,
        pdf_hash: str,
    ) -> int:
        from app.models.ai_run import AIEnrichmentRun

        async with self._session_factory() as session:
            run = AIEnrichmentRun(
                magazine_id=magazine_id,
                issue_id=issue_id,
                trigger=trigger,
                pdf_hash=pdf_hash,
                status="running",
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run.id

    async def _finalize_run(
        self,
        *,
        run_id: int,
        steps: list[dict[str, Any]],
        final: dict[str, Any],
        applied_mode: str,
        elapsed_ms: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        from datetime import datetime

        from sqlalchemy import select

        from app.models.ai_run import AIEnrichmentRun

        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(AIEnrichmentRun).where(AIEnrichmentRun.id == run_id)
                )
            ).scalars().first()
            if row is None:
                return
            row.steps_json = json.dumps(steps, ensure_ascii=False)
            row.final_json = json.dumps(final, ensure_ascii=False)
            row.applied_mode = applied_mode
            row.total_elapsed_ms = elapsed_ms
            row.status = status
            row.error_message = error_message
            row.completed_at = datetime.utcnow()
            await session.commit()

    async def _finalize_skip(
        self,
        run_id: int,
        steps: list[dict[str, Any]],
        started_monotonic: float,
        reason: str,
    ) -> EnrichmentResult:
        elapsed = int((time.monotonic() - started_monotonic) * 1000)
        await self._finalize_run(
            run_id=run_id,
            steps=steps,
            final={},
            applied_mode="skipped_fallback",
            elapsed_ms=elapsed,
            status="skipped",
            error_message=reason,
        )
        return EnrichmentResult(
            final={},
            applied_mode="skipped_fallback",
            run_id=run_id,
            steps=steps,
            total_elapsed_ms=elapsed,
        )


def merge_ai_into_parsed(parsed, ai_final: dict[str, Any], mode: str) -> Any:
    """Apply AI extraction to a Parsed dataclass per autorité mode.

    ``parsed`` : the object returned by ``parse_magazine_filename``.
    Fields we override : title, number, year, month, day, is_hs
    (mapped to `is_special` on Issue downstream), series_number.

    ``mode`` :
      - ``remplace``  : any AI non-null value wins over parsed
      - ``complete``  : AI fills in only when parsed field is null
      - ``propose``   : parsed untouched (proposals table handles it)
      - anything else : no-op (defensive)
    """
    if mode in ("propose", "skipped_fallback") or not ai_final:
        return parsed

    field_map = {
        "title": "title",
        "issue_number": "number",
        "year": "year",
        "month": "month",
        "day": "day",
    }
    for ai_key, parsed_key in field_map.items():
        ai_val = ai_final.get(ai_key)
        if ai_val is None:
            continue
        current = getattr(parsed, parsed_key, None)
        if mode == "remplace":
            setattr(parsed, parsed_key, ai_val)
        elif mode == "complete" and current is None:
            setattr(parsed, parsed_key, ai_val)
    return parsed
