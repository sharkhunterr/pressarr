"""``/api/v1/system/filesystem`` — server-side directory browser.

Porté depuis romarr avec 2 enrichissements par entrée (bookkeepy le
user demandait « le détail du contenu ») :

  * ``child_count`` : nombre de sous-entrées non cachées (fichiers +
    dossiers). Cap à 5000 pour éviter les listings monstrueux.
  * ``is_writable`` : os.access(path, W_OK). Sert à faire ressortir
    tout de suite si le root folder envisagé est utilisable en écriture.

Deux modes selon le paramètre ``path`` :

  * ``path`` omis ou ``/`` → liste curated des candidats habituels
    (``/magazines``, ``/downloads``, ``/config``, ``/mnt``, ``/media``…).
  * ``path=/<dir>`` → sous-répertoires directs (dossiers uniquement,
    dotfiles filtrés).

Pas d'auth : pressarr n'a pas de système user aujourd'hui. Le blocklist
`_FORBIDDEN_PREFIXES` protège les chemins sensibles kernel/init.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/system/filesystem", tags=["System"])


# Hard block sur les chemins qui exposent l'init/kernel/etc — pas d'usage
# opérateur légitime pour un root folder de magazines.
_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "/proc",
    "/sys",
    "/dev",
    "/boot",
    "/etc",
    "/root",
    "/run",
    "/tmp",
    "/var/log",
    "/var/lib/docker",
)

# Top-level surface le picker propose en priorité. Ordre = ordre d'affichage.
# Ceux qui n'existent pas dans le container sont simplement omis.
_LIKELY_MOUNTS: tuple[str, ...] = (
    "/magazines",   # défaut pressarr
    "/downloads",
    "/config",
    "/mnt",
    "/media",
    "/data",
    "/library",
    "/srv",
    "/opt",
    "/home",
    "/app",
)

# Plafond pour ``child_count`` — un listing de 200k fichiers bloquerait
# le picker sans intérêt informatif. On dit "5000+" au-delà.
_CHILD_COUNT_CAP = 5000


class Entry(BaseModel):
    """Une entrée dans un listing."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    path: str
    """Chemin absolu — passer verbatim comme ``?path=`` pour descendre."""
    is_dir: bool = True
    is_mount: bool = Field(
        default=False,
        alias="isMount",
        description=(
            "True quand cette entrée est sur un système de fichiers "
            "différent de son parent — indicateur fort qu'il s'agit "
            "d'un volume Docker `-v` monté ici."
        ),
    )
    child_count: int | None = Field(
        default=None,
        alias="childCount",
        description=(
            "Nombre d'items directs (fichiers + dossiers) dans ce "
            "dossier. Null si la lecture a échoué (permission denied "
            "typiquement). Capé à 5000 — au delà on ne compte plus."
        ),
    )
    is_writable: bool = Field(
        default=False,
        alias="isWritable",
        description="os.access(path, W_OK) — le processus peut-il écrire ici.",
    )

    model_config = ConfigDict(populate_by_name=True)


class ListingResponse(BaseModel):
    """Une réponse de listing."""

    path: str
    parent: str | None
    entries: list[Entry]


def _is_forbidden(resolved: Path) -> bool:
    s = str(resolved)
    return any(
        s == prefix or s.startswith(prefix + "/") for prefix in _FORBIDDEN_PREFIXES
    )


def _count_children(path: Path) -> int | None:
    """Compte les enfants directs, capé à ``_CHILD_COUNT_CAP``. Renvoie
    None sur erreur — le FE affichera '?' plutôt que 0."""
    n = 0
    try:
        for _ in path.iterdir():
            n += 1
            if n >= _CHILD_COUNT_CAP:
                return _CHILD_COUNT_CAP
        return n
    except OSError:
        return None


def _entry_from_path(path: Path, parent_dev: int | None = None) -> Entry:
    try:
        st = path.stat()
        is_mount = parent_dev is not None and st.st_dev != parent_dev
    except OSError:
        is_mount = False
    return Entry(
        name=path.name or str(path),
        path=str(path),
        is_dir=True,
        is_mount=is_mount,
        child_count=_count_children(path),
        is_writable=os.access(path, os.W_OK),
    )


@router.get(
    "",
    response_model=ListingResponse,
    summary="Lister les sous-dossiers d'un chemin.",
)
async def list_directory(
    path: Annotated[str, Query()] = "/",
) -> ListingResponse:
    raw = path.strip() or "/"
    try:
        target = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid path: {e}",
        ) from e

    if _is_forbidden(target):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"path {str(target)!r} is not browsable",
        )

    # Root curated : filter _LIKELY_MOUNTS aux existants.
    if str(target) == "/":
        entries: list[Entry] = []
        for candidate in _LIKELY_MOUNTS:
            p = Path(candidate)
            if p.is_dir():
                entries.append(_entry_from_path(p))
        return ListingResponse(path="/", parent=None, entries=entries)

    if not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"path {str(target)!r} not found",
        )
    if not target.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"path {str(target)!r} is not a directory",
        )

    try:
        parent_dev: int | None = target.stat().st_dev
    except OSError:
        parent_dev = None

    entries = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith("."):
                continue
            try:
                if not child.is_dir():
                    continue
            except OSError:
                continue  # broken symlink
            if _is_forbidden(child.resolve()):
                continue
            entries.append(_entry_from_path(child, parent_dev=parent_dev))
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"permission denied on {str(target)!r}",
        ) from e
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to list {str(target)!r}: {e}",
        ) from e

    parent = str(target.parent) if target != Path("/") else None
    return ListingResponse(path=str(target), parent=parent, entries=entries)


__all__ = ["router"]
