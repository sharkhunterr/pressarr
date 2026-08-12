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


def _arbitrate(
    torrent: dict[str, Any],
    vision_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge torrent (primary) + vision outputs (fill nulls only).

    Rule set — strict, deterministic, no LLM :
      - Chaque champ du torrent non-null gagne, PÉRIODE. On ne remplace
        jamais une valeur torrent par une valeur vision (évite les
        hallucinations vision de venir polluer un torrent bien parsé).
      - Si `title` est null côté torrent → prend le title vision.
        Normalisation légère : `L'ÉQUIPE` (all caps vision) → `L'Équipe`
        (title case) pour matcher les magazines en DB.
      - Si `issue_number` est null → prend celui de la première vision
        output qui en fournit un.
      - Date : si year/month/day sont tous non-null côté torrent, on
        garde tout. Sinon on parse `date_text` vision (best-effort,
        formats français courants) et on remplit UNIQUEMENT les
        champs manquants.
      - `is_hs` : garde la valeur torrent (bool, jamais null).
      - `series_number` : garde la valeur torrent.
      - `confidence` : moyenne pondérée (torrent 0.7, vision 0.3)
        basée sur le ratio de champs non-null.
    """
    out: dict[str, Any] = {
        "title": torrent.get("title"),
        "issue_number": torrent.get("issue_number"),
        "year": torrent.get("year"),
        "month": torrent.get("month"),
        "day": torrent.get("day"),
        "is_hs": bool(torrent.get("is_hs")),
        "series_number": torrent.get("series_number"),
    }

    # Cherche la première vision output utile pour chaque champ.
    for entry in vision_outputs:
        vd = entry.get("data") if isinstance(entry, dict) else {}
        if not isinstance(vd, dict):
            continue
        if out["title"] is None and vd.get("title"):
            out["title"] = _normalise_title(str(vd["title"]))
        if out["issue_number"] is None:
            iv = vd.get("issue_number")
            if isinstance(iv, int):
                out["issue_number"] = iv
            elif isinstance(iv, str):
                # Extract les chiffres — la vision renvoie parfois
                # « N° 26290 » ou « 26 290 » avec espace.
                digits = "".join(ch for ch in iv if ch.isdigit())
                if digits:
                    try:
                        out["issue_number"] = int(digits)
                    except ValueError:
                        pass
        # Date : uniquement si torrent n'a pas TOUT.
        if not all(out.get(k) is not None for k in ("year", "month", "day")):
            date_text = vd.get("date_text")
            if isinstance(date_text, str):
                y, m, d = _parse_french_date(date_text)
                if y and out.get("year") is None:
                    out["year"] = y
                if m and out.get("month") is None:
                    out["month"] = m
                if d and out.get("day") is None:
                    out["day"] = d

    # Confidence : ratio de champs non-null pondéré.
    core_fields = ["title", "issue_number", "year", "month", "day"]
    non_null = sum(1 for f in core_fields if out.get(f) is not None)
    out["confidence"] = round(non_null / len(core_fields), 2)
    return out


_MONTHS_FR = {
    "janvier": 1, "jan": 1,
    "février": 2, "fevrier": 2, "fev": 2, "févr": 2,
    "mars": 3, "mar": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "août": 8, "aout": 8,
    "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "décembre": 12, "decembre": 12, "dec": 12, "déc": 12,
}


def _parse_french_date(text: str) -> tuple[int | None, int | None, int | None]:
    """Best-effort parse d'une date FR — accepte plusieurs formats :

    - « lundi 10 août 2026 »  → (2026, 8, 10)
    - « 15 janvier 2025 »     → (2025, 1, 15)
    - « Mars 2024 »           → (2024, 3, None)
    - « 2016-04-23 »          → (2016, 4, 23)
    - « 2016-4-23 »           → (2016, 4, 23)
    - « 12/08/2026 »          → (2026, 8, 12)

    Renvoie (year, month, day) avec des None quand introuvable.
    Jamais raise — sortie tuple(None, None, None) en cas d'échec.
    """
    if not text:
        return None, None, None
    import re
    txt = text.lower().strip()

    # ISO-like : YYYY-M-D
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", txt)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return y, mo, d

    # DD/MM/YYYY
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", txt)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return y, mo, d

    # « [DD] MONTHNAME YYYY »
    year_m = re.search(r"\b(19\d{2}|20\d{2})\b", txt)
    year = int(year_m.group(1)) if year_m else None
    month = None
    for name, num in _MONTHS_FR.items():
        if name in txt:
            month = num
            break
    day_m = re.search(r"\b(\d{1,2})\b", txt)
    day = int(day_m.group(1)) if day_m and 1 <= int(day_m.group(1)) <= 31 else None

    # Guard : si le jour "match" est en fait l'année tronquée, ignore.
    if day and year and day == year % 100:
        day = None
    return year, month, day


def _normalise_title(raw: str) -> str:
    """Normalise a vision-extracted title.

    Vision LLMs souvent renvoient en MAJUSCULES (`L'ÉQUIPE`). Le
    matcher fuzzy est case-insensitive donc pas critique, mais pour
    l'affichage on préfère `L'Équipe` façon éditeur.
    """
    stripped = raw.strip()
    if not stripped:
        return stripped
    # Si TOUT en majuscules → title case avec conservation apostrophes/accents
    if stripped == stripped.upper():
        # `L'ÉQUIPE` → `L'Équipe` : capitalize chaque « mot » séparé par
        # apostrophes ou espaces.
        parts = []
        buf = ""
        for ch in stripped:
            if ch in " '-":
                if buf:
                    parts.append(buf[0] + buf[1:].lower())
                    buf = ""
                parts.append(ch)
            else:
                buf += ch
        if buf:
            parts.append(buf[0] + buf[1:].lower())
        return "".join(parts)
    return stripped


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


def _render_page_png(pdf_path: Path, page_index_1based: int, dpi: int = 250) -> bytes:
    """Render a single PDF page to PNG bytes.

    ``page_index_1based`` : 1 = first page ; negative counts from the
    end (-1 = last). ``dpi`` : 250 est un bon compromis pour la
    lisibilité des petits nombres/dates sur la couverture (numéros
    d'édition à 4-5 chiffres type « N° 26 290 » que 150 DPI rendait
    illisibles pour minicpm-v). Coût : image ~2.5× plus grosse (donc
    upload base64 + inference vision un peu plus lents), mais la
    précision d'extraction en vaut largement la peine.
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
        force: bool = False,
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
        # `force=True` bypasse le cache — utilisé quand l'user relance
        # explicitement (bouton « Refresh IA… »). Sinon on retourne
        # le dernier run success identique instantanément.
        if not force:
            cached = await self._lookup_cache(magazine_id, pdfhash)
            if cached is not None:
                cb("cache", "hit — utilisation du dernier résultat validé")
                return EnrichmentResult(
                    final=cached["final"],
                    applied_mode="cache_hit",
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

        # --- 5. Arbitre : merge Python déterministe ---------------
        # Historique : on faisait un 3e appel LLM pour merger torrent
        # + vision. Le LLM (mistral:7b) ignorait sa propre règle
        # « torrent primaire » et gardait des valeurs vision fausses
        # (ex. year=2016 hallucinée par la vision au lieu de year=2026
        # du torrent). Coût : +45s pour un résultat MOINS fiable.
        # Fix : arbitrage en code. Règle stricte : torrent > vision.
        # Vision ne remplit QUE les champs null du torrent. La date
        # vision text (« lundi 10 août 2026 ») est parsée en year/
        # month/day uniquement si tous les 3 sont null côté torrent.
        if vision_outputs:
            cb("arbiter", "Fusion déterministe (Python)")
            arb_start = time.monotonic()
            final = _arbitrate(text_result or {}, vision_outputs)
            steps.append({
                "step": "arbiter",
                "model": "deterministic-python",
                "output": final,
                "error": None,
                "elapsed_ms": int((time.monotonic() - arb_start) * 1000),
            })
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

            # History event so the run is visible in the timeline. Best-
            # effort — a FK violation on magazine_id/issue_id must not
            # break the run save.
            try:
                from app.services.history_service import create_event
                # Summarise the run for the history UI : keep only the
                # non-null fields from `final` + per-step statuses.
                summary_fields = {
                    k: v for k, v in (final or {}).items()
                    if v is not None and v != "" and v != []
                }
                step_summary = [
                    {
                        "step": s.get("step"),
                        "model": s.get("model"),
                        "page": s.get("page"),
                        "error": s.get("error"),
                        "output": s.get("output"),
                        "elapsed_ms": s.get("elapsed_ms"),
                    }
                    for s in (steps or [])
                ]
                await create_event(
                    session,
                    event_type="ai_enrichment",
                    magazine_id=row.magazine_id,
                    issue_id=row.issue_id,
                    details=(
                        f"IA enrichissement · {status} · "
                        f"{len(step_summary)} étape(s) · {elapsed_ms}ms"
                    ),
                    data={
                        "run_id": run_id,
                        "trigger": row.trigger,
                        "status": status,
                        "applied_mode": applied_mode,
                        "final": summary_fields,
                        "steps": step_summary,
                        "error_message": error_message,
                        "total_elapsed_ms": elapsed_ms,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "History event for AI run %s failed: %s", run_id, exc
                )
                try:
                    await session.rollback()
                    # Retry the AI run save without the history event.
                    row = (
                        await session.execute(
                            select(AIEnrichmentRun).where(AIEnrichmentRun.id == run_id)
                        )
                    ).scalars().first()
                    if row:
                        row.steps_json = json.dumps(steps, ensure_ascii=False)
                        row.final_json = json.dumps(final, ensure_ascii=False)
                        row.applied_mode = applied_mode
                        row.total_elapsed_ms = elapsed_ms
                        row.status = status
                        row.error_message = error_message
                        row.completed_at = datetime.utcnow()
                except Exception:  # noqa: BLE001
                    pass
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
