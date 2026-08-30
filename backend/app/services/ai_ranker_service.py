"""AI search ranker — picks the best release from a candidate list.

Two-stage tournament :
  1. Split the top-K candidates from the native scorer into batches
     of ``batch_size`` (default 5).
  2. Ask the text LLM to pick the best of each batch — small
     context = small models don't drift.
  3. If more than one batch survives (i.e. any batch picked a
     candidate), run a final round with the batch winners to
     select the overall best.

Rejection semantics : the LLM may return ``picked_index: null``
for any batch it deems entirely off-topic. If ALL batches reject,
we surface that to the caller so the auto-grab loop skips this
release rather than firing on a garbage match.

Autorité modes (``ai_ranker_mode``) :
  - ``ai_wins``       : the AI's pick overrides the scorer's top-1
  - ``ai_veto_only``  : the AI can REJECT the scorer's top-1 but
                       cannot promote a lower-ranked candidate
  - ``ai_advisory``   : the AI is called and logged but the caller
                       still receives the scorer's top-1
                       (observation mode — default)

Cache : keyed on ``(pattern_id, sha256(sorted GUIDs))``. If the
same candidate list is re-searched (e.g. hourly cron with no new
releases), we skip the LLM call entirely and return the last
result.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from app.services.ai_ollama_adapter import OllamaAdapter, OllamaError

logger = logging.getLogger(__name__)


ProgressCb = Callable[[str, str], None]


@dataclass
class RankerCandidate:
    """Minimal shape the ranker needs.

    Per the user requirement, only ``title`` and ``publish_date``
    are sent to the LLM. ``id`` and ``guid`` are opaque to the LLM
    but kept so the caller can map back to the source object
    (release, prowlarr result, ...).
    """

    id: str  # opaque id / GUID for correlation
    title: str
    publish_date: str | None  # ISO-formatted string or None


@dataclass
class RankerResult:
    """Return value of ``rank()``.

    ``final_pick_index`` : index into the original candidate list of
    the winner (0-based), or None if all candidates were rejected /
    the pipeline fell back.
    ``applied_mode`` : "ai_wins" | "ai_veto_only" | "ai_advisory" |
    "skipped_fallback".
    ``vetoed_top`` : true only when mode is ``ai_veto_only`` and the
    AI rejected the scorer's top-1 — the caller should skip this
    release entirely.
    """

    final_pick_index: int | None
    scorer_top_index: int | None
    applied_mode: str
    vetoed_top: bool
    confidence: float | None
    reason: str | None
    run_id: int
    batches: list[dict[str, Any]] = field(default_factory=list)
    total_elapsed_ms: int = 0


def candidates_hash(candidates: Sequence[RankerCandidate]) -> str:
    """SHA-256 over the sorted candidate IDs.

    Sort ensures the hash is order-independent so re-ranking the
    same set doesn't re-hit the LLM. Empty candidates → deterministic
    hash of "" so cache lookups behave sensibly.
    """
    ids = sorted(c.id for c in candidates)
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()


class AIRankerService:
    """Owns the ranker pipeline. Stateless between calls."""

    def __init__(self, config, session_factory) -> None:
        self._config = config
        self._session_factory = session_factory
        self._ollama = OllamaAdapter(
            url=config.ai_ollama_url, timeout_s=config.ai_ollama_timeout_s
        )

    async def rank(
        self,
        candidates: list[RankerCandidate],
        magazine_id: int | None,
        pattern_id: int | None,
        magazine_title_hint: str | None,
        issue_hint: str | None,
        progress_cb: ProgressCb | None = None,
        issue_id: int | None = None,
        magazine_context: dict[str, Any] | None = None,
    ) -> RankerResult:
        """Rank the candidates.

        ``magazine_title_hint`` + ``issue_hint`` are passed to the
        LLM as ground truth (« voici ce qu'on cherche »). Without
        those, small models drift toward any plausibly-titled
        release. Both may be None if the caller doesn't have them ;
        the LLM will do its best on titles alone.
        """
        cfg = self._config
        cb = progress_cb or (lambda s, d: None)
        t0 = time.monotonic()

        # Empty / too-small list — no point calling LLM. Return
        # scorer top-1 (index 0 since the caller pre-sorts).
        if not candidates:
            return RankerResult(
                final_pick_index=None,
                scorer_top_index=None,
                applied_mode="skipped_fallback",
                vetoed_top=False,
                confidence=None,
                reason="empty candidate list",
                run_id=0,
                total_elapsed_ms=0,
            )
        if len(candidates) < 2:
            # Only one candidate — nothing to rank.
            return RankerResult(
                final_pick_index=0,
                scorer_top_index=0,
                applied_mode=cfg.ai_ranker_mode,
                vetoed_top=False,
                confidence=1.0,
                reason="single candidate",
                run_id=0,
                total_elapsed_ms=0,
            )

        # Truncate to top_k — the caller sends a scored list, we
        # only ask the LLM about the head so ranker latency stays
        # bounded.
        top_k = min(cfg.ai_ranker_top_k, len(candidates))
        subset = candidates[:top_k]
        chash = candidates_hash(subset)

        # --- Cache ---------------------------------------------
        cached = await self._lookup_cache(pattern_id, chash)
        if cached is not None:
            cb("cache", "hit — pas de nouvel appel IA")
            return RankerResult(
                final_pick_index=cached["ai_picked_index"],
                scorer_top_index=cached["scorer_top_index"],
                applied_mode=cached["applied_mode"],
                vetoed_top=(
                    cfg.ai_ranker_mode == "ai_veto_only"
                    and cached["ai_picked_index"] is None
                ),
                confidence=cached["confidence"],
                reason=cached["reason"],
                run_id=cached["id"],
                total_elapsed_ms=cached["total_elapsed_ms"],
            )

        # --- Create run row ------------------------------------
        run_id = await self._create_run_row(
            magazine_id=magazine_id,
            pattern_id=pattern_id,
            candidates_hash=chash,
            candidates=subset,
        )

        # --- Guard : Ollama available + model present ----------
        available = await self._ollama.list_models()
        if not available or cfg.ai_text_model not in available:
            cb("skip", "Ollama ou modèle absent — fallback scorer natif")
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._finalize_run(
                run_id=run_id,
                batches=[],
                final={},
                applied_mode="skipped_fallback",
                scorer_top_index=0,
                ai_picked_index=None,
                confidence=None,
                reason="ollama or model unavailable",
                elapsed_ms=elapsed,
                status="skipped",
                model_used=cfg.ai_text_model,
                issue_id=issue_id,
                magazine_title_hint=magazine_title_hint,
                issue_hint=issue_hint,
            )
            return RankerResult(
                final_pick_index=0,
                scorer_top_index=0,
                applied_mode="skipped_fallback",
                vetoed_top=False,
                confidence=None,
                reason="ollama or model unavailable",
                run_id=run_id,
                total_elapsed_ms=elapsed,
            )

        # --- Round 1 : split into batches ----------------------
        bs = max(2, cfg.ai_ranker_batch_size)
        batches_raw: list[list[RankerCandidate]] = [
            subset[i:i + bs] for i in range(0, len(subset), bs)
        ]
        batches_recorded: list[dict[str, Any]] = []
        round1_winners: list[tuple[int, RankerCandidate, float, str]] = []

        for bi, batch in enumerate(batches_raw, 1):
            cb("ranker", f"Batch {bi}/{len(batches_raw)} ({len(batch)} candidats)")
            out, step = await self._call_batch(
                batch=batch,
                magazine_title_hint=magazine_title_hint,
                issue_hint=issue_hint,
                batch_index=bi,
                magazine_context=magazine_context,
            )
            batches_recorded.append(step)
            if out is None:
                continue
            picked_local = out.get("picked_index")
            confidence = float(out.get("confidence") or 0.0)
            reason = str(out.get("reason") or "")
            if (
                picked_local is None
                or not isinstance(picked_local, int)
                or picked_local < 0
                or picked_local >= len(batch)
            ):
                continue
            # Map batch-local index back to full-subset index
            global_idx = (bi - 1) * bs + picked_local
            round1_winners.append((global_idx, batch[picked_local], confidence, reason))

        # --- All batches rejected ------------------------------
        if not round1_winners:
            cb("done", "Tous les batches ont rejeté — pas de pick IA")
            elapsed = int((time.monotonic() - t0) * 1000)
            applied = cfg.ai_ranker_mode
            await self._finalize_run(
                run_id=run_id,
                batches=batches_recorded,
                final={"picked_index": None, "reason": "all batches rejected"},
                applied_mode=applied,
                scorer_top_index=0,
                ai_picked_index=None,
                confidence=0.0,
                reason="all batches rejected",
                elapsed_ms=elapsed,
                status="success",
                model_used=cfg.ai_text_model,
                issue_id=issue_id,
                magazine_title_hint=magazine_title_hint,
                issue_hint=issue_hint,
            )
            return self._project_result(
                run_id=run_id,
                mode=applied,
                scorer_top_index=0,
                ai_picked_index=None,
                confidence=0.0,
                reason="all batches rejected",
                batches=batches_recorded,
                elapsed_ms=elapsed,
            )

        # --- Round 2 : if multiple winners, arbitrate them -----
        if len(round1_winners) == 1:
            final_global_idx, _, conf, reason = round1_winners[0]
        else:
            cb("ranker", f"Round final ({len(round1_winners)} finalistes)")
            final_batch = [w[1] for w in round1_winners]
            out, step = await self._call_batch(
                batch=final_batch,
                magazine_title_hint=magazine_title_hint,
                issue_hint=issue_hint,
                batch_index=99,
                is_final=True,
                magazine_context=magazine_context,
            )
            batches_recorded.append(step)
            if (
                out is None
                or out.get("picked_index") is None
                or not isinstance(out.get("picked_index"), int)
                or out["picked_index"] < 0
                or out["picked_index"] >= len(final_batch)
            ):
                # Final round failed — fall back on best round-1 confidence
                round1_winners.sort(key=lambda t: t[2], reverse=True)
                final_global_idx, _, conf, reason = round1_winners[0]
                reason = f"final round failed; fallback: {reason}"
            else:
                pick = out["picked_index"]
                final_global_idx = round1_winners[pick][0]
                conf = float(out.get("confidence") or 0.0)
                reason = str(out.get("reason") or "")

        # --- Confidence threshold ------------------------------
        if conf < cfg.ai_ranker_confidence_threshold:
            reason = f"below threshold ({conf:.2f}); {reason}"
            final_global_idx = None

        # --- Persist -------------------------------------------
        elapsed = int((time.monotonic() - t0) * 1000)
        applied = cfg.ai_ranker_mode
        await self._finalize_run(
            run_id=run_id,
            batches=batches_recorded,
            final={
                "picked_index": final_global_idx,
                "confidence": conf,
                "reason": reason,
            },
            applied_mode=applied,
            scorer_top_index=0,
            ai_picked_index=final_global_idx,
            confidence=conf,
            reason=reason,
            elapsed_ms=elapsed,
            status="success",
            model_used=cfg.ai_text_model,
            issue_id=issue_id,
            magazine_title_hint=magazine_title_hint,
            issue_hint=issue_hint,
        )
        return self._project_result(
            run_id=run_id,
            mode=applied,
            scorer_top_index=0,
            ai_picked_index=final_global_idx,
            confidence=conf,
            reason=reason,
            batches=batches_recorded,
            elapsed_ms=elapsed,
        )

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------

    def _project_result(
        self,
        *,
        run_id: int,
        mode: str,
        scorer_top_index: int,
        ai_picked_index: int | None,
        confidence: float | None,
        reason: str | None,
        batches: list[dict[str, Any]],
        elapsed_ms: int,
    ) -> RankerResult:
        """Apply the autorité mode to derive `final_pick_index` + veto.

        Keeps the "what the AI said" separate from "what the caller
        should do" — mode logic lives here so hooks stay dumb.
        """
        if mode == "ai_wins":
            final_pick = ai_picked_index if ai_picked_index is not None else scorer_top_index
            vetoed = False
        elif mode == "ai_veto_only":
            if ai_picked_index is None:
                final_pick = None
                vetoed = True
            elif ai_picked_index == scorer_top_index:
                final_pick = scorer_top_index
                vetoed = False
            else:
                # AI wants something else — but veto-only mode says
                # we don't promote lower-ranked. Accept scorer's top,
                # no veto (AI can't reject when it has a candidate in
                # mind, only when it rejects everything).
                final_pick = scorer_top_index
                vetoed = False
        else:  # ai_advisory (or unknown)
            final_pick = scorer_top_index
            vetoed = False
        return RankerResult(
            final_pick_index=final_pick,
            scorer_top_index=scorer_top_index,
            applied_mode=mode,
            vetoed_top=vetoed,
            confidence=confidence,
            reason=reason,
            run_id=run_id,
            batches=batches,
            total_elapsed_ms=elapsed_ms,
        )

    async def _call_batch(
        self,
        *,
        batch: list[RankerCandidate],
        magazine_title_hint: str | None,
        issue_hint: str | None,
        batch_index: int,
        is_final: bool = False,
        magazine_context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        cfg = self._config
        t0 = time.monotonic()
        cand_lines = "\n".join(
            f"  [{i}] title={c.title!r} publish_date={c.publish_date!r}"
            for i, c in enumerate(batch)
        )
        header = "Round FINAL" if is_final else f"Batch {batch_index}"
        hint = ""
        if magazine_title_hint:
            hint += f"\nMagazine attendu : {magazine_title_hint}"
        if issue_hint:
            hint += f"\nNuméro attendu : {issue_hint}"

        # Contexte magazine enrichi : fréquence, jours exclus/weekend,
        # rules include/exclude, formats de date attendus. Sans ça
        # l'IA voit juste "Le Monde 30/08/2026" et pique un release
        # aléatoire qui contient "Le Monde" et un chiffre. Le context
        # complet lui permet de rejeter les off-topic (packs génériques,
        # numéros d'une autre date, dates hors du weekend combiné, etc.).
        if magazine_context:
            ctx = magazine_context
            if ctx.get("frequency"):
                hint += f"\nFréquence : {ctx['frequency']}"
            if ctx.get("excluded_days"):
                _wd = ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"]
                names = [_wd[d] for d in ctx["excluded_days"] if 0 <= d < 7]
                hint += f"\nJours EXCLUS (pas d'édition) : {', '.join(names)}"
            if ctx.get("weekend_days"):
                _wd = ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"]
                names = [_wd[d] for d in ctx["weekend_days"] if 0 <= d < 7]
                hint += (
                    f"\nÉdition WEEKEND combinée (une seule issue pour ces "
                    f"jours consécutifs) : {', '.join(names)}"
                )
            if ctx.get("expected_dates"):
                hint += (
                    f"\nFormats de date ACCEPTABLES pour cette issue : "
                    + " · ".join(ctx["expected_dates"])
                )
            if ctx.get("include_rules"):
                hint += (
                    f"\nRules INCLUDE (le titre doit contenir au moins un) : "
                    + " · ".join(ctx["include_rules"])
                )
            if ctx.get("exclude_rules"):
                hint += (
                    f"\nRules EXCLUDE (rejeter si le titre matche) : "
                    + " · ".join(ctx["exclude_rules"])
                )

        prompt = (
            f"{cfg.ai_ranker_prompt}\n\n---\n{header}{hint}\n"
            f"Candidats ({len(batch)}) :\n{cand_lines}"
        )
        step: dict[str, Any] = {
            "batch_index": batch_index,
            "is_final": is_final,
            "model": cfg.ai_text_model,
            "candidates": [
                {"id": c.id, "title": c.title, "publish_date": c.publish_date}
                for c in batch
            ],
            "output": None,
            "error": None,
            "elapsed_ms": 0,
        }
        try:
            out = await self._ollama.generate_json(
                model=cfg.ai_text_model,
                prompt=prompt,
            )
            step["output"] = out
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            return out, step
        except OllamaError as exc:
            step["error"] = str(exc)
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            logger.warning("Ranker batch %s failed: %s", batch_index, exc)
            return None, step

    async def _lookup_cache(
        self, pattern_id: int | None, chash: str
    ) -> dict[str, Any] | None:
        if pattern_id is None:
            return None
        from sqlalchemy import select

        from app.models.ai_run import AIRankerRun

        async with self._session_factory() as session:
            q = (
                select(AIRankerRun)
                .where(
                    AIRankerRun.pattern_id == pattern_id,
                    AIRankerRun.candidates_hash == chash,
                    AIRankerRun.status == "success",
                )
                .order_by(AIRankerRun.started_at.desc())
                .limit(1)
            )
            row = (await session.execute(q)).scalars().first()
            if not row:
                return None
            return {
                "id": row.id,
                "ai_picked_index": row.ai_picked_index,
                "scorer_top_index": row.scorer_top_index,
                "applied_mode": row.applied_mode,
                "confidence": row.confidence,
                "reason": row.reason,
                "total_elapsed_ms": row.total_elapsed_ms,
            }

    async def _create_run_row(
        self,
        *,
        magazine_id: int | None,
        pattern_id: int | None,
        candidates_hash: str,
        candidates: list[RankerCandidate],
    ) -> int:
        from app.models.ai_run import AIRankerRun

        async with self._session_factory() as session:
            row = AIRankerRun(
                magazine_id=magazine_id,
                pattern_id=pattern_id,
                candidates_hash=candidates_hash,
                candidates_json=json.dumps(
                    [
                        {"id": c.id, "title": c.title, "publish_date": c.publish_date}
                        for c in candidates
                    ],
                    ensure_ascii=False,
                ),
                status="running",
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row.id

    async def _finalize_run(
        self,
        *,
        run_id: int,
        batches: list[dict[str, Any]],
        final: dict[str, Any],
        applied_mode: str,
        scorer_top_index: int | None,
        ai_picked_index: int | None,
        confidence: float | None,
        reason: str | None,
        elapsed_ms: int,
        status: str,
        model_used: str,
        issue_id: int | None = None,
        magazine_title_hint: str | None = None,
        issue_hint: str | None = None,
    ) -> None:
        from datetime import datetime

        from sqlalchemy import select

        from app.models.ai_run import AIRankerRun

        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(AIRankerRun).where(AIRankerRun.id == run_id)
                )
            ).scalars().first()
            if row is None:
                return
            row.batches_json = json.dumps(batches, ensure_ascii=False)
            row.final_json = json.dumps(final, ensure_ascii=False)
            row.applied_mode = applied_mode
            row.scorer_top_index = scorer_top_index
            row.ai_picked_index = ai_picked_index
            row.confidence = confidence
            row.reason = reason
            row.total_elapsed_ms = elapsed_ms
            row.status = status
            row.model_used = model_used
            row.completed_at = datetime.utcnow()

            # History event — best-effort, ne bloque pas si FK échoue.
            try:
                from app.services.history_service import create_event
                await create_event(
                    session,
                    event_type="ai_ranker",
                    magazine_id=row.magazine_id,
                    issue_id=issue_id,
                    details=(
                        f"IA ranker · {status} · "
                        f"ai_pick={ai_picked_index} conf={confidence} · "
                        f"{len(batches)} batch(es) · {elapsed_ms}ms"
                    ),
                    data={
                        "run_id": run_id,
                        "status": status,
                        "applied_mode": applied_mode,
                        "model_used": model_used,
                        "scorer_top_index": scorer_top_index,
                        "ai_picked_index": ai_picked_index,
                        "confidence": confidence,
                        "reason": reason,
                        "batches": batches,
                        "final": final,
                        "total_elapsed_ms": elapsed_ms,
                        # Target explicite pour l'UI — évite au user
                        # de deviner "pour quelle issue ce run a tourné".
                        "target_magazine": magazine_title_hint,
                        "target_issue": issue_hint,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "History event for ranker run %s failed: %s", run_id, exc
                )
                try:
                    await session.rollback()
                except Exception:  # noqa: BLE001
                    pass

            await session.commit()
