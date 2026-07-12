"""Scene magazine importer.

JD2's Folder Watch picks up each ``.crawljob`` pressarr writes
and downloads the file(s) into
``<jdownloader_output_path>/<packageName>/``. ``packageName`` is
set to the magazine title (see ``jdownloader_dispatcher.py``),
so the layout we walk here is:

  /downloads/jd2/complete/
    Picsou Magazine/
      Picsou_Magazine_N594.pdf
    L'Équipe/
      L'Equipe_du_03-06-2026.pdf

For each top-level folder we look up the matching Magazine
(case-insensitive title match), pull every release in
``status='grabbed'`` for that magazine, and for each newly-
arrived file pick the best release to pair it with. The file
is then handed to ``import_file`` (existing helper) which
applies the naming template and copies / moves it into the
magazine's root folder. Finally the release flips to
``status='imported'`` so the next importer cycle skips it.

Idempotent: if a file has already been imported (no matching
``grabbed`` release left), it stays where it is. Operator
can manually drop the JD2 folder + re-grab if they want a
clean replay.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.magazine import Magazine
from app.models.magazine_release import MagazineRelease
from app.models.root_folder import RootFolder
from app.services.import_service import import_file

logger = logging.getLogger(__name__)


_NUMBER_FROM_LABEL_RE = re.compile(r"(\d{1,5})")


def _slug(title: str) -> str:
    """Lowercase, non-alphanumerics stripped — used to match
    the magazine title against JD2's package-folder name (JD2
    sometimes sanitises spaces / accents)."""
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def _parse_number(release: MagazineRelease) -> int | None:
    """Best-effort issue number from the release's
    ``issue_label`` first, falling back to the title. Returns
    None when the release is date-shaped (dailies)."""
    for source in (release.issue_label, release.title):
        if not source:
            continue
        m = _NUMBER_FROM_LABEL_RE.search(source)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _file_format(path: Path) -> str:
    """File extension without the dot, lowercased; "pdf" when
    the extension is missing — matches what the scrapers
    advertise."""
    return (path.suffix.lstrip(".") or "pdf").lower()


async def run_scene_import(db: AsyncSession, config) -> dict[str, int]:
    """One pass over the JD2 output folder. Returns
    ``{ "scanned": …, "imported": …, "skipped": … }`` so the
    scheduler can log meaningful summary lines."""
    stats = {"scanned": 0, "imported": 0, "skipped": 0}
    if not getattr(config, "jdownloader_enabled", False):
        return stats
    output_root = Path((config.jdownloader_output_path or "").strip())
    if not output_root.is_dir():
        return stats

    # Index every magazine by slug so we can resolve JD2's
    # package-folder name back to its row.
    magazines = (
        await db.scalars(select(Magazine))
    ).all()
    by_slug: dict[str, Magazine] = {_slug(m.title): m for m in magazines}

    for child in sorted(output_root.iterdir()):
        if not child.is_dir():
            continue
        magazine = by_slug.get(_slug(child.name))
        if magazine is None:
            logger.debug(
                "Scene import: JD2 folder %r doesn't match any magazine; "
                "leaving in place",
                child.name,
            )
            continue
        try:
            stats["imported"] += await _import_magazine_folder(
                db, magazine, child, config
            )
            stats["scanned"] += 1
        except Exception:
            logger.exception(
                "Scene import failed for %r → %s", child.name, magazine.title
            )
            stats["skipped"] += 1

    if stats["scanned"] or stats["imported"]:
        logger.info(
            "Scene importer pass: scanned=%(scanned)d "
            "imported=%(imported)d skipped=%(skipped)d",
            stats,
        )
    return stats


async def _import_magazine_folder(
    db: AsyncSession,
    magazine: Magazine,
    folder: Path,
    config,
) -> int:
    """Pair the files inside ``folder`` with grabbed releases
    for ``magazine`` and import each pair. Returns the count
    of files imported in this pass."""

    # Files we'll consider — skip part / tmp artefacts JD2 still
    # owns (extensions ``.part``, ``.crdownload`` etc).
    candidates = [
        p
        for p in folder.iterdir()
        if p.is_file()
        and not p.name.startswith(".")
        and p.suffix.lower()
        not in {".part", ".crdownload", ".tmp", ".lnk"}
    ]
    if not candidates:
        return 0

    # Releases still waiting for import. Newest-grabbed first
    # so newer-issued files line up with newer releases when
    # multiple grabs are pending (operator hit Grab repeatedly).
    grabbed = (
        await db.scalars(
            select(MagazineRelease)
            .where(
                MagazineRelease.magazine_id == magazine.id,
                MagazineRelease.status == "grabbed",
            )
            .order_by(MagazineRelease.grabbed_at.desc())
        )
    ).all()
    if not grabbed:
        # Nothing to claim these files — leave them for next
        # cycle in case the dispatcher writes another release
        # later.
        return 0

    # Root folder for this magazine (where ``import_file`` will
    # write).
    root = await db.get(RootFolder, magazine.root_folder_id)
    library_path = Path(root.path) if root else Path("/magazines")

    imported = 0
    # Greedy pairing: for each file, claim the earliest
    # unclaimed grabbed release. Good enough — operators rarely
    # grab more than 1-2 issues per magazine per cycle.
    remaining_releases = list(grabbed)
    for file_path in sorted(candidates, key=lambda p: p.stat().st_mtime):
        if not remaining_releases:
            break
        release = remaining_releases.pop(0)
        try:
            dest = await import_file(
                file_path=file_path,
                library_path=library_path,
                magazine_title=magazine.title,
                naming_template=config.naming_template,
                number=_parse_number(release),
                year=release.year,
                file_format=_file_format(file_path),
                language=(magazine.language or release.language or "unknown"),
                import_mode=config.import_mode or "copy",
            )
        except Exception as e:
            logger.warning(
                "Scene import: failed to copy %s for release id=%s: %s",
                file_path, release.id, e,
            )
            release.status = "failed"
            release.status_message = f"Import failed: {e!s}"[:500]
            await db.commit()
            continue

        release.status = "imported"
        release.status_message = f"Imported as {dest.name}"
        release.grabbed_at = release.grabbed_at or datetime.utcnow()
        try:
            from app.services.history_service import create_event

            await create_event(
                db,
                event_type="imported",
                magazine_id=magazine.id,
                details=f"Imported (scene): {dest.name}",
                data={
                    "release_id": release.id,
                    "release_title": release.title,
                    "source": release.source,
                    "library_path": str(dest),
                    "source_file": file_path.name,
                },
            )
        except Exception:
            logger.debug(
                "Scene import: history event write failed", exc_info=True
            )
        await db.commit()
        imported += 1
        logger.info(
            "Scene import: %s → %s (magazine id=%s, release id=%s)",
            file_path.name, dest, magazine.id, release.id,
        )

    return imported
