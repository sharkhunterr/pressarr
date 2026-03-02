"""Root folder management endpoints."""

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.magazine import Magazine
from app.models.root_folder import RootFolder
from app.schemas import CamelModel

router = APIRouter(prefix="/api/v1/rootfolder", tags=["Root Folders"])


class RootFolderResource(CamelModel):
    id: int
    path: str
    is_default: bool
    free_space: int = 0
    total_space: int = 0


class RootFolderCreateResource(CamelModel):
    path: str
    is_default: bool = False


@router.get("", response_model=list[RootFolderResource])
async def list_root_folders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RootFolder))
    folders = result.scalars().all()
    resources = []
    for f in folders:
        free = 0
        total = 0
        try:
            usage = shutil.disk_usage(f.path)
            free = usage.free
            total = usage.total
        except OSError:
            pass
        resources.append(
            RootFolderResource(
                id=f.id, path=f.path, is_default=f.is_default,
                free_space=free, total_space=total,
            )
        )
    return resources


@router.post("", response_model=RootFolderResource, status_code=201)
async def create_root_folder(
    body: RootFolderCreateResource,
    db: AsyncSession = Depends(get_db),
):
    path = Path(body.path)
    if not path.is_absolute():
        raise HTTPException(422, "Path must be absolute")
    if not path.exists():
        raise HTTPException(422, f"Path does not exist: {body.path}")

    existing = await db.execute(
        select(RootFolder).where(RootFolder.path == body.path)
    )
    if existing.scalars().first():
        raise HTTPException(409, "Root folder already exists")

    folder = RootFolder(path=body.path, is_default=body.is_default)
    db.add(folder)
    await db.flush()

    try:
        usage = shutil.disk_usage(body.path)
        free, total = usage.free, usage.total
    except OSError:
        free, total = 0, 0

    return RootFolderResource(
        id=folder.id, path=folder.path, is_default=folder.is_default,
        free_space=free, total_space=total,
    )


@router.delete("/{folder_id}", status_code=204)
async def delete_root_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RootFolder).where(RootFolder.id == folder_id)
    )
    folder = result.scalars().first()
    if not folder:
        raise HTTPException(404, "Root folder not found")

    # Check if in use
    mag_count = (
        await db.execute(
            select(func.count(Magazine.id)).where(
                Magazine.root_folder_id == folder_id
            )
        )
    ).scalar() or 0
    if mag_count > 0:
        raise HTTPException(409, f"Root folder is in use by {mag_count} magazine(s)")

    await db.delete(folder)
