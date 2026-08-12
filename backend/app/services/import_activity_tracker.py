"""In-memory tracker for post-download import + AI enrichment activities.

Once a download client finishes a torrent, the pipeline moves through :
  1. AI enrichment (optional, multi-step : text LLM → vision LLM → arbiter)
  2. Metadata parse + issue match
  3. File copy/move + rename
  4. Cover extraction

None of these steps have any visibility in the queue UI — from the user's
POV the item just sits at 100 % "completed" for 30-60s (AI can be much
longer) then quietly disappears once imported. This tracker fills that
gap : each stage pushes a step, the queue endpoint reads them, the UI
shows a live "importing…" row per file.

Kept intentionally small (single file, no DB) — activities live only
until the import wraps up, then auto-cleanup after 30s.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# Steps we surface — keep the vocabulary short so the UI can style them.
STEP_LABELS = {
    "queued": "En attente d'import",
    "ai_text": "IA · analyse nom torrent",
    "ai_switch_vision": "IA · chargement modèle vision",
    "ai_vision": "IA · OCR couverture",
    "ai_switch_text": "IA · rechargement modèle texte",
    "ai_arbiter": "IA · arbitrage",
    "ai_skipped": "IA · sautée (fallback parser)",
    "parse": "Analyse du nom de fichier",
    "match": "Correspondance magazine + issue",
    "copy": "Copie du fichier",
    "cover": "Extraction de la couverture",
    "notify": "Notification",
    "done": "Terminé",
    "error": "Erreur",
}


@dataclass
class ImportActivity:
    """A single import job's lifecycle steps."""

    activity_id: str  # unique — usually the download_id or a uuid
    file_name: str
    magazine_id: int | None = None
    issue_id: int | None = None
    magazine_title: str | None = None
    status: str = "running"  # running | success | failed
    current_step: str = "queued"
    current_label: str = STEP_LABELS["queued"]
    hint: str | None = None  # ex. « OCR page 1/3 »
    steps: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None


class ImportActivityTracker:
    """Singleton in-memory registry.

    Add via ``register``, update with ``push_step``, mark done with
    ``mark_done`` / ``mark_error``. Auto-cleaned after 30 s so a burst
    of imports doesn't clog the queue forever.
    """

    _AUTO_CLEANUP_S = 30

    def __init__(self) -> None:
        self._items: dict[str, ImportActivity] = {}

    def register(
        self,
        activity_id: str,
        file_name: str,
        magazine_id: int | None = None,
        issue_id: int | None = None,
        magazine_title: str | None = None,
    ) -> ImportActivity:
        item = ImportActivity(
            activity_id=activity_id,
            file_name=file_name,
            magazine_id=magazine_id,
            issue_id=issue_id,
            magazine_title=magazine_title,
        )
        self._items[activity_id] = item
        logger.info("[import-tracker] register %s — %s", activity_id, file_name)
        return item

    def push_step(
        self,
        activity_id: str,
        step: str,
        hint: str | None = None,
    ) -> None:
        """Update the current step + append to history.

        Unknown ``step`` names are surfaced verbatim (label = step)
        so callers don't have to pre-register their vocabulary.
        """
        item = self._items.get(activity_id)
        if not item:
            return
        label = STEP_LABELS.get(step, step)
        item.current_step = step
        item.current_label = label
        item.hint = hint
        item.steps.append({
            "step": step,
            "label": label,
            "hint": hint,
            "at": datetime.now().isoformat(),
        })

    def mark_done(self, activity_id: str, hint: str | None = None) -> None:
        item = self._items.get(activity_id)
        if not item:
            return
        item.status = "success"
        item.completed_at = datetime.now()
        item.current_step = "done"
        item.current_label = STEP_LABELS["done"]
        item.hint = hint
        item.steps.append({
            "step": "done", "label": STEP_LABELS["done"], "hint": hint,
            "at": item.completed_at.isoformat(),
        })

    def mark_error(self, activity_id: str, message: str) -> None:
        item = self._items.get(activity_id)
        if not item:
            return
        item.status = "failed"
        item.completed_at = datetime.now()
        item.current_step = "error"
        item.current_label = STEP_LABELS["error"]
        item.error_message = message
        item.steps.append({
            "step": "error", "label": STEP_LABELS["error"], "hint": message,
            "at": item.completed_at.isoformat(),
        })

    def get(self, activity_id: str) -> ImportActivity | None:
        return self._items.get(activity_id)

    def get_all(self) -> list[ImportActivity]:
        return list(self._items.values())

    def cleanup(self) -> int:
        """Drop items completed more than ``_AUTO_CLEANUP_S`` seconds ago.

        Returns the number of items removed. Called from queue endpoint.
        """
        cutoff = datetime.now() - timedelta(seconds=self._AUTO_CLEANUP_S)
        stale = [
            aid for aid, it in self._items.items()
            if it.completed_at and it.completed_at < cutoff
        ]
        for aid in stale:
            del self._items[aid]
        return len(stale)


tracker = ImportActivityTracker()
