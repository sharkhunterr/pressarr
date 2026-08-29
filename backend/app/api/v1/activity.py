"""Activity API — vue unifiée des actions asynchrones.

Remplace à terme /queue (garde le legacy comme redirect). Filtres :
  - ``kind``      : download | direct_download | import | analyze | scan | scheduled
  - ``status``    : queued | running | success | failed | cancelled
  - ``magazineId`` : ne renvoie que les activités liées à ce magazine
  - ``issueId``   : idem par issue

Par défaut : les activités terminées dans la dernière minute restent
visibles (fenêtre configurable dans ``activity_service``) — évite les
disparitions brutales d'items juste terminés dans l'UI.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import CamelModel
from app.services import activity_service

router = APIRouter(prefix="/api/v1/activity", tags=["Activity"])


class ActivityResource(CamelModel):
    id: int
    kind: str
    status: str
    magazine_id: int | None = None
    issue_id: int | None = None
    title: str
    subtitle: str | None = None
    progress: float
    status_message: str | None = None
    steps: list[dict[str, Any]] = []
    payload: dict[str, Any] = {}
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class ActivityCountersResource(CamelModel):
    queued: int = 0
    running: int = 0
    recent: int = 0  # terminées dans VISIBLE_S dernières secondes
    total: int = 0


VALID_KINDS = {
    "download", "direct_download", "import",
    "analyze", "ai_refresh",
    "search", "grab", "pack_grab", "pack_dispatch",
    "scan", "scheduled",
}
VALID_STATUSES = {"queued", "running", "success", "failed", "cancelled"}


@router.get("", response_model=list[ActivityResource])
async def list_activities(
    kind: str | None = Query(None),
    status: str | None = Query(None),
    magazine_id: int | None = Query(None, alias="magazineId"),
    issue_id: int | None = Query(None, alias="issueId"),
    pack_id: int | None = Query(None, alias="packId"),
    limit: int = Query(100, ge=1, le=500),
):
    """Liste des activités filtrées.

    ``status=running`` inclut par défaut aussi les activités terminées
    dans la dernière minute pour éviter les flickers UI. Passer
    ``status=history`` désactive ce comportement (renvoie strictement
    ``success|failed|cancelled``).
    """
    kinds = None
    if kind:
        if "," in kind:
            kinds = [k.strip() for k in kind.split(",") if k.strip() in VALID_KINDS]
        elif kind not in VALID_KINDS:
            raise HTTPException(400, f"Invalid kind. Expected one of {VALID_KINDS}")

    statuses = None
    include_recent = True
    if status == "history":
        statuses = ["success", "failed", "cancelled"]
        include_recent = False
    elif status:
        if "," in status:
            statuses = [s.strip() for s in status.split(",") if s.strip() in VALID_STATUSES]
        elif status not in VALID_STATUSES:
            raise HTTPException(400, f"Invalid status. Expected one of {VALID_STATUSES} or 'history'")

    # Le cleanup opportuniste s'exécutait ici à chaque GET (polling
    # 2 s par le frontend × sidebar+page+panels = ~5 appels/s).
    # Chaque cleanup prenait le _write_lock → serialisait les
    # writes activity → cascade de lock waits. Le scheduler tourne
    # déjà toutes les 5 min ; on n'a pas besoin d'un cleanup à
    # chaque GET. Cleanup UNIQUEMENT via le scheduler + boot.

    rows = await activity_service.list_activities(
        kind=kind if (kind and kinds is None) else None,
        kinds=kinds,
        status=status if (status and statuses is None and status != "history") else None,
        statuses=statuses,
        magazine_id=magazine_id,
        issue_id=issue_id,
        pack_id=pack_id,
        include_recent_terminal=include_recent,
        limit=limit,
    )
    return [ActivityResource(**activity_service.to_dict(r)) for r in rows]


@router.get("/counters", response_model=ActivityCountersResource)
async def get_counters():
    """Compteurs pour le badge sidebar (queued + running)."""
    return ActivityCountersResource(**await activity_service.counters())


@router.get("/{activity_id}", response_model=ActivityResource)
async def get_activity(activity_id: int):
    row = await activity_service.get(activity_id)
    if not row:
        raise HTTPException(404, "Activity not found")
    return ActivityResource(**activity_service.to_dict(row))


@router.post("/{activity_id}/cancel", response_model=ActivityResource)
async def cancel_activity(activity_id: int):
    row = await activity_service.get(activity_id)
    if not row:
        raise HTTPException(404, "Activity not found")
    await activity_service.cancel(activity_id)
    row = await activity_service.get(activity_id)
    return ActivityResource(**activity_service.to_dict(row))


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(activity_id: int):
    """Supprime définitivement une activité de l'historique.

    Utilisé par le bouton « Supprimer » dans la vue historique. Refuse
    les activités encore en cours (queued/running) pour ne pas laisser
    d'orphelins — utiliser POST /cancel d'abord si besoin.
    """
    row = await activity_service.get(activity_id)
    if not row:
        raise HTTPException(404, "Activity not found")
    if row.status in ("queued", "running"):
        raise HTTPException(
            409,
            "Activité en cours — annulez-la d'abord (POST /cancel)",
        )
    from sqlalchemy import delete
    from app.models.activity import Activity as _Activity
    # Activities vivent dans leur PROPRE DB (pressarr-activity.db)
    # depuis l'isolation activity — utiliser le session_factory du
    # service, pas celui de la DB principale sinon le DELETE
    # opère sur une table vide (bug apparent "delete ne marche pas").
    _sf = activity_service._session_factory()
    async with _sf() as session:
        await session.execute(delete(_Activity).where(_Activity.id == activity_id))
        await session.commit()


@router.delete("", status_code=204)
async def bulk_delete_history(
    kind: str | None = Query(None),
    older_than_days: int | None = Query(None, alias="olderThanDays"),
):
    """Purge en masse des activités terminées.

    Sans paramètre : purge TOUT l'historique success/failed/cancelled.
    ``kind`` : cible un type précis. ``olderThanDays`` : garde les
    plus récentes. Refuse les activités encore vivantes.
    """
    from datetime import datetime, timedelta

    from sqlalchemy import delete
    from app.models.activity import Activity as _Activity
    # Activities vivent dans leur PROPRE DB (pressarr-activity.db)
    # depuis l'isolation activity — utiliser le session_factory du
    # service, pas celui de la DB principale sinon le DELETE
    # opère sur une table vide (bug apparent "delete ne marche pas").
    _sf = activity_service._session_factory()
    filters = [_Activity.status.in_(["success", "failed", "cancelled"])]
    if kind:
        if kind not in VALID_KINDS:
            raise HTTPException(400, f"Invalid kind {kind}")
        filters.append(_Activity.kind == kind)
    if older_than_days is not None and older_than_days >= 0:
        cutoff = datetime.now() - timedelta(days=older_than_days)
        filters.append(_Activity.completed_at < cutoff)
    async with _sf() as session:
        await session.execute(delete(_Activity).where(*filters))
        await session.commit()
