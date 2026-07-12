"""JDownloader 2 queue inspection API.

No JD2 RPC integration — that requires either My JDownloader
(cloud + paired account) or the External Interface extension
(manual install via noVNC). Both add operator friction.

Instead, pressarr inspects the file-system state shared with
JD2 through the folder-watch contract:

- ``folderwatch/`` holds ``.crawljob`` files pressarr has
  dispatched. A pending file means JD2 hasn't ingested it
  yet (Folder Watch disabled, JD2 paused, or just slow).
- ``output_path/`` holds JD2's finished downloads in
  per-magazine folders (``packageName`` from the crawljob).

The two surfaces together cover the lifecycle:
``available → grabbed (.crawljob written) → JD2 picks it up
(file disappears from folderwatch) → JD2 downloads (file
appears in output_path/<title>/) → pressarr imports (file
moves into the library + release flips to imported)``.

REST surface:

- ``GET   /jdownloader/state`` : current snapshot
- ``DELETE /jdownloader/folderwatch/{filename}`` : drop a
  queued crawljob (release stays ``grabbed``; re-grab from
  the magazine detail page re-writes it)
- ``POST  /jdownloader/folderwatch/clear`` : wipe every
  pending crawljob in one call (useful when the operator
  wants to reset after toggling Folder Watch in JD2)
- ``POST  /jdownloader/output/{folder}/clear`` : delete a
  completed-download folder JD2 left behind that pressarr
  has already imported.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_config
from app.schemas import CamelModel as BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jdownloader", tags=["JDownloader"])


class CrawljobItem(BaseModel):
    """One pending crawljob file in folderwatch/."""

    filename: str
    package_name: str | None = None
    download_folder: str | None = None
    text_url_count: int = 0
    primary_url: str | None = None
    release_id: int | None = None
    written_at_ms: int


class CompletedFolder(BaseModel):
    """One per-magazine folder under output_path/."""

    folder_name: str
    file_count: int
    total_size_bytes: int
    files: list[CompletedFile]


class CompletedFile(BaseModel):
    name: str
    size_bytes: int
    is_part: bool


CompletedFolder.model_rebuild()


class JDownloaderState(BaseModel):
    enabled: bool
    folderwatch_path: str
    output_path: str
    folderwatch_exists: bool
    output_exists: bool
    pending_jobs: list[CrawljobItem]
    completed_folders: list[CompletedFolder]


_RELEASE_COMMENT_RE = re.compile(r"pressarr:release=(\d+)")


def _parse_crawljob(path: Path) -> CrawljobItem:
    """Cheap key=value parser — JD2's format is line-by-line
    so we don't need a real parser. Falls back gracefully when
    fields are missing (older crawljobs from before single-URL
    fix etc.)."""
    fields: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if "=" not in line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            fields[key.strip()] = value
    except OSError:
        pass

    text = fields.get("text") or ""
    # Comment carries ``pressarr:release=<id>`` — the
    # correlator the dispatcher embeds so we can match a
    # crawljob back to the DB row even after the file was
    # renamed.
    rid: int | None = None
    m = _RELEASE_COMMENT_RE.search(fields.get("comment") or "")
    if m:
        try:
            rid = int(m.group(1))
        except ValueError:
            rid = None

    # ``text=`` can contain multiple URLs separated by \n in
    # the historical multi-mirror crawljobs — count them so the
    # UI can flag legacy jobs at a glance.
    urls = [u for u in text.split() if u.startswith("http")]
    primary = urls[0] if urls else None

    return CrawljobItem(
        filename=path.name,
        package_name=fields.get("packageName"),
        download_folder=fields.get("downloadFolder"),
        text_url_count=len(urls),
        primary_url=primary,
        release_id=rid,
        written_at_ms=int(path.stat().st_mtime * 1000)
        if path.exists()
        else 0,
    )


def _list_completed(root: Path) -> list[CompletedFolder]:
    out: list[CompletedFolder] = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        files: list[CompletedFile] = []
        total = 0
        for f in sorted(child.iterdir()):
            if not f.is_file():
                continue
            size = f.stat().st_size
            total += size
            files.append(
                CompletedFile(
                    name=f.name,
                    size_bytes=size,
                    # JD2 writes ``.part`` while a download is
                    # in progress and renames once complete.
                    is_part=f.suffix.lower() in {".part", ".crdownload"},
                )
            )
        out.append(
            CompletedFolder(
                folder_name=child.name,
                file_count=len(files),
                total_size_bytes=total,
                files=files,
            )
        )
    return out


@router.get("/state", response_model=JDownloaderState)
async def get_state(config=Depends(get_config)) -> JDownloaderState:
    fw = Path(config.jdownloader_folderwatch or "")
    out = Path(config.jdownloader_output_path or "")

    pending: list[CrawljobItem] = []
    if fw.is_dir():
        for f in sorted(fw.iterdir()):
            if f.is_file() and f.suffix == ".crawljob":
                pending.append(_parse_crawljob(f))

    return JDownloaderState(
        enabled=bool(getattr(config, "jdownloader_enabled", False)),
        folderwatch_path=str(fw),
        output_path=str(out),
        folderwatch_exists=fw.is_dir(),
        output_exists=out.is_dir(),
        pending_jobs=pending,
        completed_folders=_list_completed(out),
    )


@router.delete("/folderwatch/{filename}")
async def delete_folderwatch_job(
    filename: str, config=Depends(get_config)
) -> dict:
    """Drop one pending crawljob. Safe path-strip so the
    operator can't escape the folderwatch directory."""
    safe = Path(filename).name
    if safe != filename or not safe.endswith(".crawljob"):
        raise HTTPException(400, "Invalid crawljob filename")
    fw = Path(config.jdownloader_folderwatch or "")
    target = fw / safe
    if not target.is_file():
        raise HTTPException(404, "Crawljob not found")
    try:
        target.unlink()
    except OSError as e:
        raise HTTPException(500, str(e)) from e
    return {"deleted": safe}


@router.post("/folderwatch/clear")
async def clear_folderwatch(config=Depends(get_config)) -> dict:
    """Wipe every pending crawljob. Per-release status on
    ``magazine_release`` is left alone — they stay ``grabbed``
    so the operator can re-grab from the UI to regenerate a
    crawljob. (Resetting status here would race with JD2 if it
    has already ingested some.)"""
    fw = Path(config.jdownloader_folderwatch or "")
    if not fw.is_dir():
        return {"deleted": 0}
    deleted = 0
    for f in fw.iterdir():
        if f.is_file() and f.suffix == ".crawljob":
            try:
                f.unlink()
                deleted += 1
            except OSError:
                logger.warning(
                    "JDownloader folderwatch clear: could not unlink %s",
                    f,
                )
    return {"deleted": deleted}


@router.delete("/output/{folder_name}")
async def delete_output_folder(
    folder_name: str, config=Depends(get_config)
) -> dict:
    """Drop a per-magazine completed-download folder. Use after
    pressarr's importer has copied the file into the library and
    JD2 isn't going to need the source anymore."""
    safe = Path(folder_name).name
    if safe != folder_name:
        raise HTTPException(400, "Invalid folder name")
    out = Path(config.jdownloader_output_path or "")
    target = out / safe
    if not target.is_dir():
        raise HTTPException(404, "Folder not found")
    try:
        import shutil

        shutil.rmtree(target)
    except OSError as e:
        raise HTTPException(500, str(e)) from e
    return {"deleted": safe}
