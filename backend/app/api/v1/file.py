"""Global file manager endpoints.

Aggregate view over every ``IssueFile`` in the system for the future
front-end "File Manager" page. Existing per-issue actions
(``PUT /issue/reassign``, ``DELETE /issue/{id}/file``, etc.) already
cover mutations — this router only adds the LIST endpoint and a
lightweight per-file DELETE by IssueFile id (existing delete route
needs an issue_id and won't work on unassigned files).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import Base  # noqa: F401 — register on metadata
from app.dependencies import get_db
from app.models.issue import Issue
from app.models.issue_file import IssueFile
from app.models.magazine import Magazine
from app.schemas import CamelModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/file", tags=["Files"])


# ─── Schemas ─────────────────────────────────────────────────────


class MagazineSummary(CamelModel):
    id: int
    title: str


class IssueSummary(CamelModel):
    id: int
    number: int | None
    year: int | None
    month: int | None
    day: int | None


class FileManagerRow(CamelModel):
    id: int
    filename: str
    """Nom du fichier tel qu'importé (avant renaming template)."""
    path: str
    """Chemin absolu sur disque (utile pour debug + affichage)."""
    relative_path: str
    size: int
    format: str
    quality: str
    release_group: str | None = None
    language: str | None = None
    imported_at: str
    magazine: MagazineSummary
    issue: IssueSummary | None = None
    exists_on_disk: bool = Field(
        default=True,
        description=(
            "os.path.exists(path). False si le fichier a été supprimé "
            "hors pressarr — utile pour proposer un cleanup DB."
        ),
    )


class FileManagerPage(CamelModel):
    records: list[FileManagerRow]
    page: int
    page_size: int
    total: int
    total_assigned: int
    total_unassigned: int
    total_missing_on_disk: int


# ─── LIST ────────────────────────────────────────────────────────


@router.get("", response_model=FileManagerPage)
async def list_files(
    magazine_id: int | None = Query(None, alias="magazineId"),
    assigned: Literal["all", "yes", "no"] = Query("all"),
    quality: str | None = Query(None),
    format_: str | None = Query(None, alias="format"),
    search: str | None = Query(
        None,
        description=(
            "Substring case-insensitive sur original_filename OU "
            "relative_path — pratique pour retrouver un fichier par nom."
        ),
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> FileManagerPage:
    """Liste paginée de tous les IssueFile avec filtres."""

    filters = []
    if magazine_id is not None:
        filters.append(IssueFile.magazine_id == magazine_id)
    if assigned == "yes":
        filters.append(IssueFile.issue_id.is_not(None))
    elif assigned == "no":
        filters.append(IssueFile.issue_id.is_(None))
    if quality:
        filters.append(IssueFile.quality == quality)
    if format_:
        filters.append(IssueFile.format == format_)
    if search:
        needle = f"%{search.lower()}%"
        filters.append(
            or_(
                func.lower(IssueFile.original_filename).like(needle),
                func.lower(IssueFile.relative_path).like(needle),
            )
        )
    where = and_(*filters) if filters else None

    base_q = select(IssueFile)
    if where is not None:
        base_q = base_q.where(where)

    total_q = select(func.count()).select_from(IssueFile)
    if where is not None:
        total_q = total_q.where(where)
    total = int((await db.execute(total_q)).scalar() or 0)

    # Global aggregates (ignore filters — utile dans le header pour
    # « X assignés / Y non-assignés » globaux).
    total_assigned = int(
        (
            await db.execute(
                select(func.count()).select_from(IssueFile).where(
                    IssueFile.issue_id.is_not(None)
                )
            )
        ).scalar()
        or 0
    )
    total_unassigned = int(
        (
            await db.execute(
                select(func.count()).select_from(IssueFile).where(
                    IssueFile.issue_id.is_(None)
                )
            )
        ).scalar()
        or 0
    )

    q = (
        base_q
        .options(
            selectinload(IssueFile.magazine),
            selectinload(IssueFile.issue),
        )
        .order_by(IssueFile.imported_at.desc(), IssueFile.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await db.execute(q)).scalars().all())

    records: list[FileManagerRow] = []
    missing_on_disk = 0
    for f in rows:
        exists = os.path.exists(f.path)
        if not exists:
            missing_on_disk += 1
        mag: Magazine | None = f.magazine
        iss: Issue | None = f.issue
        records.append(
            FileManagerRow(
                id=f.id,
                filename=f.original_filename,
                path=f.path,
                relative_path=f.relative_path,
                size=f.size,
                format=f.format,
                quality=f.quality,
                release_group=f.release_group,
                language=f.language,
                imported_at=f.imported_at.isoformat(),
                magazine=MagazineSummary(
                    id=mag.id if mag else 0,
                    title=mag.title if mag else "?",
                ),
                issue=(
                    IssueSummary(
                        id=iss.id,
                        number=iss.number,
                        year=iss.year,
                        month=iss.month,
                        day=iss.day,
                    )
                    if iss
                    else None
                ),
                exists_on_disk=exists,
            )
        )

    return FileManagerPage(
        records=records,
        page=page,
        page_size=page_size,
        total=total,
        total_assigned=total_assigned,
        total_unassigned=total_unassigned,
        total_missing_on_disk=missing_on_disk,
    )


# ─── Assign / reassign / detach ─────────────────────────────────


class FileAssignBody(CamelModel):
    """Cibles possibles :
    - `issue_id` : rattache le fichier à cet issue existant.
    - `issue_id: null` + `magazine_id`      : détache (garde le fichier
       comme "unassigned" sous ce magazine).
    - `issue_id: null` sans `magazine_id`   : detach (magazine inchangé).
    """
    issue_id: int | None = None
    magazine_id: int | None = None


@router.put("/{file_id}/assign", response_model=FileManagerRow)
async def assign_file(
    file_id: int,
    body: FileAssignBody,
    db: AsyncSession = Depends(get_db),
) -> FileManagerRow:
    """Rattache/détache un IssueFile — équivalent global du
    ``PUT /issue/reassign`` / ``PUT /issue/assign-file`` existants,
    mais accepte un IssueFile.id direct (nécessaire pour les fichiers
    unassigned qui n'ont pas d'issue de départ)."""
    f = (
        await db.execute(
            select(IssueFile)
            .options(
                selectinload(IssueFile.magazine),
                selectinload(IssueFile.issue),
            )
            .where(IssueFile.id == file_id)
        )
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(404, f"IssueFile {file_id} not found")

    if body.issue_id is not None:
        target = await db.get(Issue, body.issue_id)
        if target is None:
            raise HTTPException(404, f"Issue {body.issue_id} not found")
        # L'unique(issue_id) empêche d'écraser un fichier existant.
        conflict = (
            await db.execute(
                select(IssueFile).where(
                    IssueFile.issue_id == body.issue_id,
                    IssueFile.id != file_id,
                )
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise HTTPException(
                409,
                f"Issue {body.issue_id} already has file "
                f"'{conflict.original_filename}'. Détache-la d'abord "
                f"ou supprime-la pour réassigner.",
            )
        f.issue_id = body.issue_id
        f.magazine_id = target.magazine_id
        target.status = "available"
    else:
        f.issue_id = None
        if body.magazine_id is not None:
            f.magazine_id = body.magazine_id

    await db.flush()
    await db.refresh(f, ["magazine", "issue"])
    mag: Magazine | None = f.magazine
    iss: Issue | None = f.issue
    return FileManagerRow(
        id=f.id,
        filename=f.original_filename,
        path=f.path,
        relative_path=f.relative_path,
        size=f.size,
        format=f.format,
        quality=f.quality,
        release_group=f.release_group,
        language=f.language,
        imported_at=f.imported_at.isoformat(),
        magazine=MagazineSummary(
            id=mag.id if mag else 0,
            title=mag.title if mag else "?",
        ),
        issue=(
            IssueSummary(
                id=iss.id,
                number=iss.number,
                year=iss.year,
                month=iss.month,
                day=iss.day,
            )
            if iss
            else None
        ),
        exists_on_disk=os.path.exists(f.path),
    )


# ─── Delete ──────────────────────────────────────────────────────


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: int,
    delete_on_disk: bool = Query(True, alias="deleteOnDisk"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Supprime le row IssueFile + optionnellement le fichier sur disque.

    Par défaut ``deleteOnDisk=true`` — cohérent avec l'UX « je veux
    virer ce fichier ». Passer ``false`` pour ne dropper que le row
    DB (utile pour nettoyer une entrée orpheline dont le fichier a
    déjà été supprimé hors pressarr).
    """
    f = await db.get(IssueFile, file_id)
    if f is None:
        raise HTTPException(404, f"IssueFile {file_id} not found")

    disk_path = f.path
    # Le row : delete before touching disk pour ne pas laisser d'orphan
    # DB si l'unlink échoue avec un integrity error rare.
    await db.execute(delete(IssueFile).where(IssueFile.id == file_id))
    await db.flush()

    if delete_on_disk:
        try:
            p = Path(disk_path)
            if p.exists():
                p.unlink()
        except OSError as e:
            # Non-fatal : la row DB est déjà retirée. On log pour
            # que le user puisse cleanup manuellement.
            logger.warning(
                "IssueFile %d row deleted, but on-disk unlink of %s failed: %s",
                file_id, disk_path, e,
            )
    return None
