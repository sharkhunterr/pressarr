"""Import activity tracker — thin backward-compat wrapper autour de
:mod:`app.services.activity_service` (DB persistante).

Historiquement ce tracker était un registre in-memory pur. Il est
maintenu comme façade avec la même API sync (``register``, ``push_step``,
``mark_done`` etc.) mais chaque appel écrit désormais dans la table
``Activity`` — les activités survivent aux redémarrages et alimentent
la nouvelle page Activité + le badge sidebar.

Migration path : les call sites existants (``process_downloaded_file``,
``ai.py``) continuent à fonctionner sans modification grâce à la
correspondance :
  ``register(activity_id, file_name, magazine_id, issue_id, magazine_title)``
  → crée une row Activity(kind="import", external_id=activity_id, ...)

La méthode ``get_all()`` reste dispo pour le legacy endpoint /queue
(en cours de retirement — remplacé par /activity dans la Phase 2).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services import activity_service

logger = logging.getLogger(__name__)


# Labels utilisés par le pipeline d'import — mêmes clés qu'avant pour
# minimiser les changements de call sites.
STEP_LABELS = {
    "queued": "En attente d'import",
    "ai_text": "IA · analyse nom torrent",
    "ai_switch_vision": "IA · chargement modèle vision",
    "ai_vision": "IA · OCR couverture",
    "ai_switch_text": "IA · rechargement modèle texte",
    "ai_arbiter": "IA · arbitrage",
    "ai_cache_hit": "IA · cache réutilisé (résultat validé)",
    "ai_skipped": "IA · sautée (fallback parser)",
    "parse": "Analyse du nom de fichier",
    "match": "Correspondance magazine + issue",
    "copy": "Copie du fichier",
    "cover": "Extraction de la couverture",
    "notify": "Notification",
    "done": "Terminé",
    "skipped_no_upgrade": "Déjà importé — pas de gain qualité",
    "error": "Erreur",
}


def _run_async(coro):
    """Fire-and-forget d'une coroutine depuis un contexte sync.

    Utilisé pour les appels de tracker depuis le pipeline d'import
    qui est async — mais les callbacks (progress_cb du LLM) peuvent
    être invoqués depuis des threads (asyncio.to_thread). Cette
    helper gère les 2 cas : loop courant en cours → schedule task ;
    pas de loop → run_until_complete.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        loop.create_task(coro)
    else:
        asyncio.run(coro)


class ImportActivityTracker:
    """Backward-compat façade — persiste via ActivityService.

    Le mapping activity_id (str) → Activity.id (int DB) est maintenu
    en mémoire pour le temps de vie d'un import ; il est perdu au
    redémarrage mais les activités elles-mêmes survivent.
    """

    def __init__(self) -> None:
        self._id_map: dict[str, int] = {}

    def register(
        self,
        activity_id: str,
        file_name: str,
        magazine_id: int | None = None,
        issue_id: int | None = None,
        magazine_title: str | None = None,
    ) -> None:
        async def _do():
            db_id = await activity_service.create(
                kind="import",
                title=magazine_title or file_name,
                subtitle=file_name if magazine_title else None,
                magazine_id=magazine_id,
                issue_id=issue_id,
                external_id=activity_id,
                payload={"file_name": file_name},
            )
            self._id_map[activity_id] = db_id
            logger.info(
                "[import-tracker] register %s → activity id=%d",
                activity_id, db_id,
            )
        _run_async(_do())

    def push_step(
        self,
        activity_id: str,
        step: str,
        hint: str | None = None,
    ) -> None:
        label = STEP_LABELS.get(step, step)
        async def _do():
            db_id = await self._resolve(activity_id)
            if db_id is None:
                return
            await activity_service.push_step(
                db_id,
                {"step": step, "label": label, "hint": hint},
            )
            # Progression synthétique : nb steps / total attendu.
            # ~12 étapes typique pour un import full IA.
            # Note : compte les steps SANS le pré-push (on est dedans
            # après le push, donc +0). L'ordre de grandeur reste juste.
            # Une valeur clean sera écrasée par mark_done à la fin.
            act = await activity_service.get(db_id)
            if act:
                steps_done = len(activity_service._load_steps(act.steps))
                await activity_service.update_progress(
                    db_id, min(99.0, steps_done * (100 / 12)),
                )
        _run_async(_do())

    def mark_done(self, activity_id: str, hint: str | None = None) -> None:
        async def _do():
            db_id = await self._resolve(activity_id)
            if db_id is None:
                return
            await activity_service.mark_done(db_id, hint)
            self._id_map.pop(activity_id, None)
        _run_async(_do())

    def mark_error(self, activity_id: str, message: str) -> None:
        async def _do():
            db_id = await self._resolve(activity_id)
            if db_id is None:
                return
            await activity_service.mark_error(db_id, message)
            self._id_map.pop(activity_id, None)
        _run_async(_do())

    def bind_issue(
        self,
        activity_id: str,
        *,
        magazine_id: int | None = None,
        issue_id: int | None = None,
    ) -> None:
        """Late-bind d'un magazine/issue une fois qu'il est connu.

        Utilisé quand ``process_downloaded_file`` démarre sans
        contexte (deferred grab) et découvre la cible via parser + IA.
        """
        async def _do():
            db_id = await self._resolve(activity_id)
            if db_id is None:
                return
            await activity_service.update_meta(
                db_id,
                magazine_id=magazine_id,
                issue_id=issue_id,
            )
        _run_async(_do())

    async def _resolve(self, activity_id: str) -> int | None:
        db_id = self._id_map.get(activity_id)
        if db_id is not None:
            return db_id
        # Reload from DB in case of a restart mid-import
        db_id = await activity_service.find_by_external_id(
            "import", activity_id, live_only=True,
        )
        if db_id is not None:
            self._id_map[activity_id] = db_id
        return db_id

    # ------------------------------------------------------------
    # Legacy sync accessors used by /queue endpoint. Best-effort —
    # renvoie une liste vide en cas d'erreur DB pour ne pas casser
    # l'endpoint historique pendant la migration.
    # ------------------------------------------------------------

    def get(self, activity_id: str) -> Any | None:
        db_id = self._id_map.get(activity_id)
        if db_id is None:
            return None
        try:
            return _resolve_sync(activity_service.get(db_id))
        except Exception:
            return None

    def get_all(self) -> list[Any]:
        """Legacy accessor — renvoie les activités import « vivantes ».

        Format compatible avec l'ancien registre in-memory : chaque
        item a ``.activity_id``, ``.file_name``, ``.status``,
        ``.current_label``, ``.hint``, ``.steps``, ``.magazine_id``,
        ``.magazine_title``, ``.issue_id``, ``.started_at``,
        ``.completed_at``, ``.error_message``. Utilisé par l'endpoint
        /queue historique pendant la migration Phase 2.
        """
        try:
            rows = _resolve_sync(activity_service.list_activities(
                kind="import",
                statuses=["queued", "running"],
                limit=50,
            )) or []
            return [_row_to_legacy(r) for r in rows]
        except Exception as exc:
            logger.debug("get_all import legacy accessor failed: %s", exc)
            return []

    def cleanup(self) -> int:
        try:
            return _resolve_sync(activity_service.cleanup_stale()) or 0
        except Exception:
            return 0


def _resolve_sync(coro):
    """Run an async coro synchronously, careful about existing loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Can't nest — surface as no-op. Legacy sync callers are only
        # invoked from FastAPI endpoints (sync context via to_thread)
        # or the scheduler ; both allow this.
        return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=5)
    return asyncio.run(coro)


class _LegacyItem:
    """Duck-typed accessor used by the legacy /queue endpoint."""
    def __init__(self, act):
        self.activity_id = str(act.id)
        self.file_name = act.subtitle or act.title
        self.magazine_id = act.magazine_id
        self.magazine_title = act.title if act.title != self.file_name else None
        self.issue_id = act.issue_id
        # Map DB status to old vocabulary (running | success | failed)
        s = act.status
        self.status = "success" if s == "success" else "failed" if s == "failed" else "running"
        self.current_step = None
        self.current_label = act.status_message or ""
        self.hint = None
        self.steps = activity_service._load_steps(act.steps)
        self.error_message = act.error_message
        self.started_at = act.started_at
        self.completed_at = act.completed_at


def _row_to_legacy(act) -> _LegacyItem:
    return _LegacyItem(act)


tracker = ImportActivityTracker()
