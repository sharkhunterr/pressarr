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

from pathlib import Path

from sqlalchemy import and_, desc, event, func, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app import database as _db
from app.models.activity import Activity

logger = logging.getLogger(__name__)


# ─── Dedicated activity DB (isolated from main app DB) ──────────────
#
# Activity writes concurrent avec le monitor scheduler + les
# pack_dispatch tenaient la DB principale en lock → create() tombait
# en "database is locked" malgré 8 retries × 2.4 s. Solution : activity
# vit dans SON PROPRE fichier SQLite. Zéro contention, zéro race avec
# le reste de l'app (magazines / issues / downloads). Perte assumée :
# les FK vers magazine/issue deviennent purement informatives
# (SQLite ne les vérifie pas cross-DB). C'est un tradeoff acceptable
# pour de l'observabilité qui n'a pas besoin d'intégrité relationnelle.
_activity_engine = None
_activity_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_activity_db(main_db_path: str) -> None:
    """Init le moteur SQLite dédié activity. Fichier séparé à côté de
    la DB principale : ``pressarr.db`` → ``pressarr-activity.db``.
    Crée la table si absente."""
    global _activity_engine, _activity_session_factory

    p = Path(main_db_path)
    activity_path = p.with_name(p.stem + "-activity.db")
    _activity_engine = create_async_engine(
        f"sqlite+aiosqlite:///{activity_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(_activity_engine.sync_engine, "connect")
    def _set_activity_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    _activity_session_factory = async_sessionmaker(
        _activity_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Crée la table Activity dans la nouvelle DB si absente.
    async with _activity_engine.begin() as conn:
        await conn.run_sync(Activity.metadata.create_all, tables=[Activity.__table__])
    logger.info("Activity DB initialized: %s", activity_path)


def _session_factory():
    """Retourne le factory dédié — fallback sur la DB principale au cas
    où init_activity_db n'a pas été appelé (ex. tests unitaires)."""
    if _activity_session_factory is not None:
        return _activity_session_factory
    return _db.async_session_factory


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


async def _retry_on_lock(coro_factory, tries: int = 8, delay: float = 0.3):
    """Exécute une coroutine, retry avec backoff sur DB lock.

    Défense en profondeur : le _write_lock devrait suffire, mais
    aiosqlite peut occasionnellement lever OperationalError sur des
    transactions rapides multiples (le WAL a besoin d'un checkpoint
    de temps en temps). Ancienne valeur 3×250ms=1.5s se révélait trop
    courte quand le monitor scheduler + dispatch pack + trackers
    d'imports pouvaient tenir la DB longtemps. 8 essais × backoff
    linéaire = jusqu'à ~11 s d'attente cumulée (0.3+0.6+…+2.4).

    Un write bloqué 11 s c'est déjà critique, mais mieux qu'un
    silent-drop dans le log warning qui laisse l'utilisateur voir
    "Recherche lancée" sans jamais d'activity en base.
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

    # Sérialise avec les autres writers via _write_lock + retry 3× 250 ms
    # sur "database is locked". Sans ça un create tombe silencieusement
    # dès qu'un autre writer (dispatch, scheduler, monitor) tient un
    # tx de plus de quelques ms → activités jamais persistées → user ne
    # voit rien dans /activity malgré l'action déclenchée.
    row_id_holder: dict[str, int] = {}

    async def _do() -> None:
        async with _write_lock:
            async with _session_factory()() as session:
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
                row_id_holder["id"] = row.id
                logger.info(
                    "[activity] created id=%d kind=%s title=%r",
                    row.id, kind, title,
                )

    await _retry_on_lock(_do)
    return row_id_holder["id"]


async def find_by_external_id(
    kind: str, external_id: str, live_only: bool = True,
) -> int | None:
    """Cherche une activité par ``payload.external_id``. Renvoie l'id
    ou None."""
    async with _session_factory()() as session:
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
            async with _session_factory()() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                steps = _load_steps(row.steps)
                step_with_at = {**step, "at": step.get("at") or datetime.now().isoformat()}
                steps.append(step_with_at)
                row.steps = _dump_steps(steps)
                row.updated_at = datetime.now()
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
            async with _session_factory()() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                row.progress = clamped
                row.updated_at = datetime.now()
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
            async with _session_factory()() as session:
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
            async with _session_factory()() as session:
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


def _truncate_error(message: str, max_len: int = 400) -> str:
    """Tronque + normalise un message d'erreur avant persistance.

    Beaucoup d'exceptions SQLAlchemy incluent le SQL complet + les
    paramètres échoués — dont l'``error_message`` du run PRÉCÉDENT
    quand une retry-en-boucle se met en place. Sans garde, chaque
    tour ajoute 500 chars et l'error_message finit par dépasser 20k
    chars → row bloatée + logs illisibles.

    Prend la 1re ligne (le message principal), coupe à ``max_len``.
    """
    if not message:
        return message
    first_line = message.split("\n", 1)[0].strip()
    if len(first_line) > max_len:
        first_line = first_line[:max_len - 1] + "…"
    return first_line


async def mark_error(activity_id: int, message: str) -> None:
    short = _truncate_error(message)

    async def _do():
        async with _write_lock:
            async with _session_factory()() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                row.status = "failed"
                row.completed_at = datetime.now()
                row.error_message = short
                steps = _load_steps(row.steps)
                steps.append({
                    "step": "error",
                    "label": "Erreur",
                    "hint": short,
                    "at": datetime.now().isoformat(),
                })
                row.steps = _dump_steps(steps)
                row.status_message = f"Erreur — {short}"
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
            async with _session_factory()() as session:
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


async def reopen(activity_id: int) -> None:
    """Remet en running une activité interrompue par un redémarrage,
    pour qu'un tracker reprenne la même ligne (et ses étapes) au lieu
    d'en ouvrir une nouvelle."""
    async def _do():
        async with _write_lock:
            async with _session_factory()() as session:
                row = (await session.execute(
                    select(Activity).where(Activity.id == activity_id)
                )).scalars().first()
                if not row:
                    return
                row.status = "running"
                row.completed_at = None
                await session.commit()
    await _retry_on_lock(_do)


async def cancel(activity_id: int) -> None:
    async def _do():
        async with _write_lock:
            async with _session_factory()() as session:
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
    async with _session_factory()() as session:
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
    pack_id: int | None = None,
    include_recent_terminal: bool = True,
    limit: int = 100,
) -> list[Activity]:
    """Liste filtrée.

    ``include_recent_terminal`` : quand True (défaut), les activités
    terminées dans la dernière ``VISIBLE_S`` fenêtre restent visibles
    même quand on filtre par status=running. Comme ça une activité
    qui vient de finir ne disparaît pas brutalement de la vue.
    """
    async with _session_factory()() as session:
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
        if pack_id is not None:
            # Pas de FK direct pack_id sur Activity (activities packs
            # étaient traitées comme metadata dans payload JSON). On
            # cherche le substring "pack_id": <n> dans payload —
            # même pattern que find_by_external_id.
            needle_json = f'"pack_id": {pack_id}'
            filters.append(Activity.payload.ilike(f"%{needle_json}%"))

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
            async with _session_factory()() as session:
                # Kill uniquement les activités dont la dernière mise à
                # jour (push_step / update_progress) date de > cutoff.
                # Un pack_dispatch qui tourne 30 min mais pousse un step
                # toutes les 3 min est vivant → survit. Sans ce fix,
                # cleanup_stale utilisait started_at et tuait des runs
                # actifs long.
                rows = (await session.execute(
                    select(Activity).where(
                        Activity.status == "running",
                        Activity.updated_at < cutoff,
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


async def mark_interrupted_at_boot() -> int:
    """Au boot : marque les activités "running" comme "cancelled" +
    reset les download_id de packs interrompus pour que le monitor
    re-fire la dispatch au prochain tick.

    Le process qui exécutait ces activités est mort (crash / reload
    dev / restart). On les marque `cancelled` (pas `failed` — c'est
    plus juste : ce n'est pas une vraie erreur, c'est une interruption
    externe), status_message explicite pour le user.

    Pour les pack_dispatch spécifiquement : on retire leur download_id
    du set ``_processed_downloads`` de download_service. Sans ça, le
    monitor tick considère le download comme déjà traité et ne
    re-déclenche jamais la dispatch → l'utilisateur reste bloqué avec
    32 fichiers en pending sur disque et zéro activité.

    Retourne le nombre d'activités traitées.
    """
    from app.services import download_service as _ds

    now = datetime.now()
    n = 0
    reset_download_ids: list[str] = []

    async def _do():
        nonlocal n
        async with _write_lock:
            async with _session_factory()() as session:
                rows = (await session.execute(
                    select(Activity).where(Activity.status == "running")
                )).scalars().all()
                for row in rows:
                    row.status = "cancelled"
                    row.completed_at = now
                    row.status_message = (
                        "Interrompue — process redémarré, "
                        "sera relancée par le monitor si applicable"
                    )
                    if not row.error_message:
                        row.error_message = None
                    n += 1
                    # Pack dispatch : extract download_id pour reset.
                    if row.kind == "pack_dispatch":
                        try:
                            payload = _load_payload(row.payload)
                            did = payload.get("download_id")
                            if isinstance(did, str) and did:
                                reset_download_ids.append(did)
                        except Exception:
                            pass
                if n:
                    await session.commit()

    await _retry_on_lock(_do)

    # Reset processed downloads pour que le monitor re-fire.
    if reset_download_ids:
        try:
            _ds.ensure_registry_loaded()
            for did in reset_download_ids:
                _ds._processed_downloads.discard(did)
            _ds._save_registry()
            logger.info(
                "[activity] reset %d pack download_ids from _processed_downloads",
                len(reset_download_ids),
            )
        except Exception:  # noqa: BLE001
            logger.warning("Failed to reset pack downloads", exc_info=True)

    if n:
        logger.info("[activity] marked %d running activities as cancelled at boot", n)
    return n


async def counters() -> dict[str, int]:
    """Compteurs pour le badge sidebar.

    ``queued`` + ``running`` = « en cours réel ». On y ajoute les
    activités terminées dans les ``VISIBLE_S`` dernières secondes
    (recent success/failed/cancelled) pour que le badge sidebar
    catch les grabs très rapides — sinon un grab qui dure 200 ms
    n'apparaît jamais entre deux polls 5 s.
    """
    async with _session_factory()() as session:
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
