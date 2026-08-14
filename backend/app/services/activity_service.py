"""ActivityService — CRUD + write-through cache pour la table Activity.

Remplace les trackers in-memory dispersés (import_activity_tracker,
direct_download_tracker) par un registre unifié persistant.

**API principale** :

  aid = await create(kind="import", title=..., magazine_id=..., ...)
  await push_step(aid, {"step": "ai_vision", "label": "...", "hint": "..."})
  await update_progress(aid, 42.5)
  await mark_done(aid, hint="imported to /magazines/...")
  await mark_error(aid, "quality mismatch")

**Concurrence** : chaque appel ouvre sa propre session async — sûr
depuis n'importe quelle coroutine background. Un cache par-ID à
courte durée limite les round-trips DB pendant les bursts de
push_step (typiquement 10-15 par import).

**Cleanup** :
  - Items ``success``/``failed``/``cancelled`` restent visibles
    ``VISIBLE_S`` seconds pour que l'UI les affiche brièvement
    puis passe en "historique" (renvoyés sur demande explicite).
  - Items en ``running`` depuis > ``STALE_S`` sont force-fail
    (safety net contre les processes crashés sans mark_done).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Sequence

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.exc import OperationalError

from app import database as _db
from app.models.activity import Activity

logger = logging.getLogger(__name__)


# Fenêtre pendant laquelle une activité terminée reste visible dans la
# vue « en cours ». Passée cette fenêtre, elle ne remonte plus qu'en
# vue historique.
VISIBLE_S = 60

# Delai après lequel une activité « running » sans mise à jour est
# considérée orpheline et force-marquée en failed.
STALE_S = 900


# Sérialise les WRITES activity au niveau Python.
#
# Le pipeline enrich() peut pousser 15+ push_step + update_progress
# en quelques ms depuis plusieurs coroutines concurrentes (tracker
# facade, scheduler, API polls). SQLite en WAL supporte les writes
# concurrents mais avec un busy_timeout 5 s — si une transaction se
# tient trop longtemps (grosse UPDATE steps JSON), les autres tombent
# en `database is locked`. Ce lock async met tout le monde à la
# queue → une seule transaction en vol à la fois → zéro contention.
_write_lock = asyncio.Lock()


async def _retry_on_lock(coro_factory, tries: int = 3, delay: float = 0.25):
    """Exécute une coroutine, retry avec backoff sur DB lock.

    Défense en profondeur : le _write_lock devrait suffire, mais
    aiosqlite peut occasionnellement lever OperationalError sur des
    transactions rapides multiples (le WAL a besoin d'un checkpoint
    de temps en temps). 3 tentatives × 250 ms suffit largement.
    """
    last_exc: Exception | None = None
    for attempt in range(tries):
        try:
            return await coro_factory()
        except OperationalError as exc:
            last_exc = exc
            if "database is locked" not in str(exc).lower():
                raise
            await asyncio.sleep(delay * (attempt + 1))
    if last_exc:
        raise last_exc


def _dump_steps(steps: Sequence[dict[str, Any]] | None) -> str | None:
    if not steps:
        return None
    return json.dumps(list(steps), ensure_ascii=False, default=str)


def _load_steps(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _dump_payload(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, default=str)


def _load_payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


async def create(
    *,
    kind: str,
    title: str,
    subtitle: str | None = None,
    magazine_id: int | None = None,
    issue_id: int | None = None,
    status: str = "running",
    payload: dict[str, Any] | None = None,
    external_id: str | None = None,
) -> int:
    """Insère une nouvelle activité. Retourne son id.

    ``external_id`` : si fourni, dédoublonne — si une activité même
    ``kind`` avec ce payload.external_id existe déjà en running/queued,
    la retourne au lieu d'en créer une nouvelle. Utile pour les
    trackers qui peuvent être appelés plusieurs fois pour le même
    download (monitor scheduler qui retriggere).
    """
    payload_dict = dict(payload or {})
    if external_id:
        payload_dict.setdefault("external_id", external_id)
        existing = await find_by_external_id(kind, external_id, live_only=True)
        if existing is not None:
            return existing

    async with _db.async_session_factory() as session:
        row = Activity(
            kind=kind,
            status=status,
            title=title,
            subtitle=subtitle,
            magazine_id=magazine_id,
            issue_id=issue_id,
            payload=_dump_payload(payload_dict),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        logger.info(
            "[activity] created id=%d kind=%s title=%r", row.id, kind, title,
        )
        return row.id


async def find_by_external_id(
    kind: str, external_id: str, live_only: bool = True,
) -> int | None:
    """Cherche une activité par ``payload.external_id``. Renvoie l'id
    ou None."""
    async with _db.async_session_factory() as session:
        filters = [Activity.kind == kind]
        if live_only:
            filters.append(Activity.status.in_(["queued", "running"]))
        # JSON substring match — cheap and portable. Le payload contient
        # ``"external_id": "xxx"`` — on cherche ce substring.
        needle = f'"external_id": "{external_id}"'
        filters.append(Activity.payload.ilike(f"%{needle}%"))
        row = (await session.execute(
            select(Activity).where(and_(*filters))
            .order_by(desc(Activity.id)).limit(1)
        )).scalars().first()
        return row.id if row else None


async def push_step(
    activity_id: int,
    step: dict[str, Any],
    *,
    status_message: str | None = None,
) -> None:
    """Append une step à la liste et mets à jour la status_message."""
    async def _do():
        async with _write_lock:
            async with _db.async_session_factory() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                steps = _load_steps(row.steps)
                step_with_at = {**step, "at": step.get("at") or datetime.now().isoformat()}
                steps.append(step_with_at)
                row.steps = _dump_steps(steps)
                if status_message is not None:
                    row.status_message = status_message
                else:
                    label = step.get("label") or step.get("step") or ""
                    hint = step.get("hint")
                    row.status_message = f"{label} — {hint}" if hint else label
                await session.commit()
    await _retry_on_lock(_do)


async def update_progress(
    activity_id: int,
    progress: float,
    *,
    status_message: str | None = None,
) -> None:
    """Update the progress field (0-100). Clamps out-of-range values."""
    clamped = max(0.0, min(100.0, float(progress)))
    async def _do():
        async with _write_lock:
            async with _db.async_session_factory() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                row.progress = clamped
                if status_message is not None:
                    row.status_message = status_message
                await session.commit()
    await _retry_on_lock(_do)


async def update_meta(
    activity_id: int,
    *,
    magazine_id: int | None = None,
    issue_id: int | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    payload_patch: dict[str, Any] | None = None,
) -> None:
    """Patch metadata (bind late, e.g. après enrichissement IA)."""
    async def _do():
        async with _write_lock:
            async with _db.async_session_factory() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                if magazine_id is not None:
                    row.magazine_id = magazine_id
                if issue_id is not None:
                    row.issue_id = issue_id
                if title is not None:
                    row.title = title
                if subtitle is not None:
                    row.subtitle = subtitle
                if payload_patch:
                    merged = _load_payload(row.payload)
                    merged.update(payload_patch)
                    row.payload = _dump_payload(merged)
                await session.commit()
    await _retry_on_lock(_do)


async def mark_done(activity_id: int, hint: str | None = None) -> None:
    async def _do():
        async with _write_lock:
            async with _db.async_session_factory() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                row.status = "success"
                row.progress = 100.0
                row.completed_at = datetime.now()
                steps = _load_steps(row.steps)
                steps.append({
                    "step": "done",
                    "label": "Terminé",
                    "hint": hint,
                    "at": datetime.now().isoformat(),
                })
                row.steps = _dump_steps(steps)
                row.status_message = f"Terminé — {hint}" if hint else "Terminé"
                await session.commit()
    await _retry_on_lock(_do)


async def mark_error(activity_id: int, message: str) -> None:
    async def _do():
        async with _write_lock:
            async with _db.async_session_factory() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                row.status = "failed"
                row.completed_at = datetime.now()
                row.error_message = message
                steps = _load_steps(row.steps)
                steps.append({
                    "step": "error",
                    "label": "Erreur",
                    "hint": message,
                    "at": datetime.now().isoformat(),
                })
                row.steps = _dump_steps(steps)
                row.status_message = f"Erreur — {message}"
                await session.commit()
    await _retry_on_lock(_do)


async def set_status(activity_id: int, status: str) -> None:
    """Direct patch de status (queued|running|success|failed|cancelled).

    Utilise ``mark_done``/``mark_error`` en priorité — ce helper est
    réservé aux cas où la transition n'est ni un succès terminal ni
    une erreur (ex. queued → running quand le download démarre).
    """
    async def _do():
        async with _write_lock:
            async with _db.async_session_factory() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                row.status = status
                if status in ("success", "failed", "cancelled") and row.completed_at is None:
                    row.completed_at = datetime.now()
                await session.commit()
    await _retry_on_lock(_do)


async def cancel(activity_id: int) -> None:
    async def _do():
        async with _write_lock:
            async with _db.async_session_factory() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row or row.status in ("success", "failed", "cancelled"):
                    return
                row.status = "cancelled"
                row.completed_at = datetime.now()
                row.status_message = "Annulée"
                await session.commit()
    await _retry_on_lock(_do)


async def get(activity_id: int) -> Activity | None:
    async with _db.async_session_factory() as session:
        return (await session.execute(
            select(Activity).where(Activity.id == activity_id)
        )).scalars().first()


async def list_activities(
    *,
    kind: str | None = None,
    kinds: list[str] | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    magazine_id: int | None = None,
    issue_id: int | None = None,
    include_recent_terminal: bool = True,
    limit: int = 100,
) -> list[Activity]:
    """Liste filtrée.

    ``include_recent_terminal`` : quand True (défaut), les activités
    terminées dans la dernière ``VISIBLE_S`` fenêtre restent visibles
    même quand on filtre par status=running. Comme ça une activité
    qui vient de finir ne disparaît pas brutalement de la vue.
    """
    async with _db.async_session_factory() as session:
        filters: list[Any] = []
        if kind:
            filters.append(Activity.kind == kind)
        elif kinds:
            filters.append(Activity.kind.in_(kinds))
        if status or statuses:
            wanted = statuses or [status]  # type: ignore[list-item]
            status_clause: Any = Activity.status.in_(wanted)
            if include_recent_terminal:
                terminal_cutoff = datetime.now() - timedelta(seconds=VISIBLE_S)
                status_clause = or_(
                    status_clause,
                    and_(
                        Activity.status.in_(["success", "failed", "cancelled"]),
                        Activity.completed_at >= terminal_cutoff,
                    ),
                )
            filters.append(status_clause)
        if magazine_id is not None:
            filters.append(Activity.magazine_id == magazine_id)
        if issue_id is not None:
            filters.append(Activity.issue_id == issue_id)

        stmt = select(Activity)
        if filters:
            stmt = stmt.where(and_(*filters))
        stmt = stmt.order_by(desc(Activity.started_at)).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return list(rows)


async def cleanup_stale(*, older_than_s: int = STALE_S) -> int:
    """Force-fail les activités ``running`` sans mise à jour depuis
    ``older_than_s`` secondes.

    ``completed_at`` est backdated à ``started_at + STALE_S`` (moment
    théorique du fail) pour que ces items sortent immédiatement de la
    fenêtre « recent terminal » de la vue en cours — sinon un orphelin
    de 2 h auto-failed au boot resterait affiché 60 s en « en cours »
    juste parce qu'il vient d'être marqué failed maintenant.

    Retourne le nombre marquées.

    **Plancher de sécurité 60 s** : jamais ne kill une activité de
    moins de 60 s, quelle que soit la valeur de ``older_than_s``
    demandée. Ça protège les imports fraîchement démarrés d'un
    cleanup opportuniste + laisse le temps au 1er push_step de
    landing (les early steps peuvent être lentes si SQLite est
    verrouillée par un autre writer).
    """
    now = datetime.now()
    effective_s = max(60, older_than_s)
    cutoff = now - timedelta(seconds=effective_s)
    n = 0
    async def _do():
        nonlocal n
        async with _write_lock:
            async with _db.async_session_factory() as session:
                rows = (await session.execute(
                    select(Activity).where(
                        Activity.status == "running",
                        Activity.started_at < cutoff,
                    )
                )).scalars().all()
                for row in rows:
                    row.status = "failed"
                    row.completed_at = row.started_at + timedelta(seconds=STALE_S)
                    row.error_message = (
                        row.error_message
                        or "Activité bloquée — pas de mark_done reçu"
                    )
                    row.status_message = "Erreur — Activité bloquée (auto-fail)"
                    n += 1
                if n:
                    await session.commit()
    await _retry_on_lock(_do)
    if n:
        logger.warning("[activity] auto-failed %d stale running activities", n)
    return n


async def counters() -> dict[str, int]:
    """Compteurs pour le badge sidebar.

    ``queued`` + ``running`` = « en cours réel ». On y ajoute les
    activités terminées dans les ``VISIBLE_S`` dernières secondes
    (recent success/failed/cancelled) pour que le badge sidebar
    catch les grabs très rapides — sinon un grab qui dure 200 ms
    n'apparaît jamais entre deux polls 5 s.
    """
    async with _db.async_session_factory() as session:
        live_rows = (await session.execute(
            select(Activity.status)
            .where(Activity.status.in_(["queued", "running"]))
        )).all()
        recent_cutoff = datetime.now() - timedelta(seconds=VISIBLE_S)
        recent_count = (await session.execute(
            select(func.count(Activity.id)).where(
                Activity.status.in_(["success", "failed", "cancelled"]),
                Activity.completed_at >= recent_cutoff,
            )
        )).scalar_one() or 0
    counts = {"queued": 0, "running": 0, "recent": int(recent_count), "total": 0}
    for (s,) in live_rows:
        counts[s] = counts.get(s, 0) + 1
    counts["total"] = counts["queued"] + counts["running"] + counts["recent"]
    return counts


def to_dict(row: Activity) -> dict[str, Any]:
    """Serialize an Activity row for API responses."""
    return {
        "id": row.id,
        "kind": row.kind,
        "status": row.status,
        "magazine_id": row.magazine_id,
        "issue_id": row.issue_id,
        "title": row.title,
        "subtitle": row.subtitle,
        "progress": round(row.progress, 1),
        "status_message": row.status_message,
        "steps": _load_steps(row.steps),
        "payload": _load_payload(row.payload),
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }
