"""Pack dispatch service — extraction + analyse IA + décision par fichier.

Pipeline complet d'un pack téléchargé :

  1. Extraction : détecte les archives (zip/rar/7z/tar) dans le répertoire
     de download et extrait leur contenu à côté. Les fichiers déjà
     "flat" (issu direct du torrent) sont pris tels quels.
  2. Collection : liste récursive de tous les fichiers avec extension
     supportée (pdf, epub, cbr, cbz).
  3. Analyse : pour chaque fichier, crée une row ``pack_dispatch_file``
     puis lance le pipeline IA (mêmes steps que Refresh IA sur une
     issue) — deep par défaut, shallow (parser filename only) si
     ``pack.deep_ai_analysis`` est False.
  4. Match : fuzzy match du titre extrait vs magazines existants.
     Le score de match et la source (parser/vision/arbiter/issn)
     sont journalisés pour observabilité.
  5. Décision :
       - match fort ET !preview_before_import → auto-import
       - match faible/aucun ET auto_create_missing_magazines → magazine
         placeholder + import
       - sinon → status=pending_user, l'utilisateur tranche via l'UI.

Chaque fichier apparaît dans le registre activités (kind="pack_file")
pour visibilité live dans la sidebar + panel magazine.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.magazine import Magazine
from app.models.pack import Pack
from app.models.pack_dispatch_file import PackDispatchFile
from app.parser.magazine_parser import fuzzy_match_title, parse_magazine_filename

logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = {".pdf", ".epub", ".cbr", ".cbz"}
# Seuil au-dessus duquel un fuzzy match est considéré comme "fort" et
# déclenche l'auto-import sans confirmation user (si preview OFF).
MATCH_STRONG_THRESHOLD = 78.0
# Seuil au-dessus duquel on considère qu'un match "faible" existe quand
# même — sert d'aide à la décision utilisateur (pré-sélection dans le
# dropdown).
MATCH_WEAK_THRESHOLD = 55.0


# ─── Extraction d'archive ─────────────────────────────────────────────


def _detect_archive(path: Path) -> str | None:
    """Retourne 'zip' / 'rar' / '7z' / 'tar' selon l'extension.
    None si ce n'est pas une archive (fichier direct ou dossier)."""
    if not path.is_file():
        return None
    n = path.name.lower()
    if n.endswith(".zip"):
        return "zip"
    if n.endswith(".rar"):
        return "rar"
    if n.endswith(".7z"):
        return "7z"
    if n.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz")):
        return "tar"
    return None


def extract_archive(archive_path: Path, dest_dir: Path) -> tuple[bool, str | None]:
    """Extrait ``archive_path`` dans ``dest_dir``. Retourne (success, error).

    Support :
      - zip : stdlib ``zipfile``
      - tar / tar.gz / … : stdlib ``tarfile``
      - 7z : ``py7zr`` (dépendance optionnelle)
      - rar : ``rarfile`` + binaire ``unrar`` (dépendance optionnelle)

    L'archive n'est pas supprimée après extraction — on garde une trace.
    """
    kind = _detect_archive(archive_path)
    if kind is None:
        return False, f"Format non reconnu : {archive_path.name}"

    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        if kind == "zip":
            import zipfile
            with zipfile.ZipFile(archive_path) as z:
                z.extractall(dest_dir)
        elif kind == "tar":
            import tarfile
            with tarfile.open(archive_path) as t:
                t.extractall(dest_dir)
        elif kind == "7z":
            try:
                import py7zr
            except ImportError:
                return False, "py7zr non installé — impossible d'extraire .7z"
            with py7zr.SevenZipFile(archive_path) as z:
                z.extractall(dest_dir)
        elif kind == "rar":
            try:
                import rarfile
            except ImportError:
                return False, "rarfile non installé — impossible d'extraire .rar"
            with rarfile.RarFile(archive_path) as r:
                r.extractall(dest_dir)
        return True, None
    except Exception as exc:
        logger.warning("Extraction %s a échoué : %s", archive_path.name, exc)
        return False, f"{type(exc).__name__}: {exc}"


def extract_all_archives(root: Path) -> list[tuple[Path, str | None]]:
    """Trouve toutes les archives sous ``root`` (récursif) et les extrait
    dans un sous-dossier ``<root>/_extracted/<archive_stem>/``.

    Retourne la liste (archive_path, error_or_None). Aucune erreur ne
    lève — on collecte simplement et l'appelant décide.
    """
    if root.is_file():
        candidates = [root]
    elif root.is_dir():
        candidates = [p for p in root.rglob("*") if p.is_file()]
    else:
        return []

    results: list[tuple[Path, str | None]] = []
    for cand in candidates:
        if _detect_archive(cand) is None:
            continue
        dest = root / "_extracted" / cand.stem
        # Idempotent : si dest existe déjà et n'est pas vide, on skip.
        if dest.exists() and any(dest.iterdir()):
            results.append((cand, None))
            continue
        ok, err = extract_archive(cand, dest)
        results.append((cand, err if not ok else None))
    return results


def collect_all_files(root: Path) -> list[Path]:
    """Liste récursive des fichiers avec extension supportée sous ``root``.

    Inclut les extractions faites dans ``_extracted/`` — on part du
    principe que ``extract_all_archives`` a déjà tourné.
    """
    if root.is_file():
        if root.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [root]
        return []
    if not root.is_dir():
        return []
    files = [
        p for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return files


# ─── Analyse + décision par fichier ───────────────────────────────────


async def _analyze_file_shallow(
    file_path: Path,
) -> dict[str, Any]:
    """Analyse rapide : parser filename uniquement. ~1 ms."""
    parsed = parse_magazine_filename(file_path.name)
    return {
        "title": parsed.title,
        "issue_number": parsed.number,
        "year": parsed.year,
        "month": parsed.month,
        "day": parsed.day,
        "source": "parser",
        "run_id": None,
    }


async def _analyze_file_deep(
    file_path: Path,
    config,
    session_factory,
) -> dict[str, Any]:
    """Analyse profonde : pipeline IA complet (torrent → python-OCR →
    vision → arbiter). Comme Refresh IA sur une issue. ~30-60 s / fichier
    selon hardware Ollama.

    Retourne les metadata extraites + run_id + source.
    """
    from app.services.ai_enrichment_service import AIEnrichmentService

    svc = AIEnrichmentService(config, session_factory)
    result = await svc.enrich(
        torrent_name=file_path.name,
        pdf_path=file_path,
        magazine_id=None,
        issue_id=None,
        trigger="pack_dispatch",
    )
    final = result.final or {}
    return {
        "title": final.get("title"),
        "issue_number": final.get("issue_number"),
        "year": final.get("year"),
        "month": final.get("month"),
        "day": final.get("day"),
        "issn": final.get("issn"),
        "source": "arbiter" if final else "parser",
        "run_id": result.run_id,
    }


async def _match_to_magazine(
    db: AsyncSession,
    extracted: dict[str, Any],
) -> tuple[Magazine | None, float | None, str | None]:
    """Trouve le meilleur magazine existant pour les metadata extraites.

    Priorité :
      1. ISSN exact match — infaillible si le magazine parent a l'ISSN.
      2. Fuzzy match sur title (fuzzywuzzy / RapidFuzz).

    Retourne (magazine, score, source) — tous None si aucun candidat.
    """
    issn = (extracted.get("issn") or "").strip()
    title = (extracted.get("title") or "").strip()

    if issn:
        stmt = select(Magazine).where(Magazine.issn == issn)
        mag = (await db.execute(stmt)).scalar_one_or_none()
        if mag:
            return mag, 100.0, "issn"

    if not title:
        return None, None, None

    stmt = select(Magazine)
    mags = list((await db.execute(stmt)).scalars().all())
    if not mags:
        return None, None, None
    known = [m.title for m in mags]
    hit = fuzzy_match_title(title, known, threshold=MATCH_WEAK_THRESHOLD)
    if hit is None:
        return None, None, None
    matched_title, score = hit
    mag = next((m for m in mags if m.title == matched_title), None)
    if mag is None:
        return None, None, None
    return mag, float(score), "fuzzy"


async def _create_placeholder_magazine(
    db: AsyncSession,
    pack: Pack,
    extracted: dict[str, Any],
) -> Magazine:
    """Crée un magazine placeholder à partir des metadata extraites.
    Hérite root_folder + quality_profile du pack. Frequency par défaut
    depuis ``pack.default_new_magazine_frequency``."""
    from app.services.magazine_service import generate_title_slug

    title = (extracted.get("title") or "Inconnu").strip()[:255] or "Inconnu"
    slug = generate_title_slug(title)

    # Si un magazine avec ce slug existe déjà (created par un dispatch
    # précédent dans le même pack), on le réutilise plutôt que de
    # dupliquer.
    existing = (await db.execute(select(Magazine).where(Magazine.title_slug == slug))).scalar_one_or_none()
    if existing:
        return existing

    mag = Magazine(
        title=title,
        title_slug=slug,
        issn=extracted.get("issn"),
        frequency=pack.default_new_magazine_frequency,
        monitored=True,
        root_folder_id=pack.root_folder_id,
        quality_profile_id=pack.quality_profile_id,
        is_placeholder=True,
        enrichment_status="pending",
    )
    db.add(mag)
    await db.flush()
    logger.info(
        "Pack %s auto-created placeholder magazine %s (title=%r slug=%s)",
        pack.name, mag.id, title, slug,
    )
    return mag


async def _import_file_to_magazine(
    db: AsyncSession,
    file_path: Path,
    magazine_id: int,
    config,
) -> tuple[bool, int | None, str]:
    """Importe le fichier en tant qu'issue du magazine. Réutilise
    ``process_downloaded_file`` — même code path que les grabs individuels
    donc bénéficie de l'IA enrichment, quality upgrade, blocklist, etc.

    Retourne (success, issue_id, message).
    """
    from app.services.import_service import process_downloaded_file

    result = await process_downloaded_file(
        db, file_path, config, magazine_id=magazine_id, issue_id=None,
    )
    return (
        bool(result.get("success")),
        result.get("issue_id"),
        result.get("message", ""),
    )


# ─── Orchestrateur principal ──────────────────────────────────────────


async def process_pack_download(
    db: AsyncSession,
    pack_id: int,
    download_id: str,
    save_path: Path,
    config,
    session_factory,
) -> dict[str, Any]:
    """Point d'entrée. Extraction + création des rows + analyse + décision.

    L'analyse tourne SÉQUENTIELLEMENT (l'IA vision est déjà lourde
    single-thread côté Ollama). Chaque fichier a sa propre activity_id
    dans le registre pour visibilité live.

    Retourne un dict de statistiques : {extracted, files, analyzed,
    auto_imported, placeholder_created, pending_user, errors}.
    """
    from app.services import activity_service

    pack = await db.get(Pack, pack_id)
    if pack is None:
        raise ValueError(f"pack {pack_id} not found")

    # ── 1. Extraction ────────────────────────────────────────────
    activity_id = await activity_service.create(
        kind="pack_dispatch",
        title=f"Pack {pack.name} — dispatch",
        payload={"pack_id": pack_id, "download_id": download_id},
    )
    try:
        await activity_service.push_step(
            activity_id,
            {"step": "extract", "label": "Extraction", "hint": "Décompression des archives"},
        )
        extract_results = extract_all_archives(save_path)
        extract_errors = [(p.name, e) for p, e in extract_results if e]
        if extract_errors:
            logger.info(
                "Pack %s extraction — %d erreurs (non-fatal) : %s",
                pack.name, len(extract_errors), extract_errors[:3],
            )

        # ── 2. Collection des fichiers ───────────────────────────
        await activity_service.push_step(
            activity_id,
            {"step": "collect", "label": "Listing", "hint": "Recensement des fichiers importables"},
        )
        files = collect_all_files(save_path)
        if not files:
            await activity_service.mark_done(activity_id, hint="Aucun fichier importable")
            return {
                "extracted": len(extract_results),
                "files": 0,
                "analyzed": 0,
                "auto_imported": 0,
                "placeholder_created": 0,
                "pending_user": 0,
                "errors": len(extract_errors),
            }

        # ── 3. Enregistrement des dispatch rows ──────────────────
        rows: list[PackDispatchFile] = []
        for f in files:
            existing = (
                await db.execute(
                    select(PackDispatchFile).where(
                        PackDispatchFile.pack_id == pack_id,
                        PackDispatchFile.download_id == download_id,
                        PackDispatchFile.filename == f.name,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                # Reprise d'un run précédent : on garde la row si déjà
                # résolue, sinon on réinitialise pour ré-analyse.
                if existing.status in ("imported", "ignored"):
                    continue
                existing.status = "pending_analysis"
                existing.error_message = None
                rows.append(existing)
            else:
                row = PackDispatchFile(
                    pack_id=pack_id,
                    download_id=download_id,
                    filename=f.name,
                    path=str(f),
                    size=f.stat().st_size if f.exists() else 0,
                    status="pending_analysis",
                )
                db.add(row)
                rows.append(row)
        await db.flush()

        # ── 4. Analyse + décision par fichier ─────────────────────
        stats = {
            "extracted": len(extract_results),
            "files": len(files),
            "analyzed": 0,
            "auto_imported": 0,
            "placeholder_created": 0,
            "pending_user": 0,
            "errors": len(extract_errors),
        }
        for idx, row in enumerate(rows, start=1):
            file_path = Path(row.path)
            await activity_service.push_step(
                activity_id,
                {
                    "step": "analyze",
                    "label": f"Analyse {idx}/{len(rows)}",
                    "hint": row.filename,
                },
            )
            try:
                await activity_service.update_progress(
                    activity_id, (idx - 1) * 100 / max(1, len(rows)),
                )
            except Exception:
                pass
            try:
                extracted = (
                    await _analyze_file_deep(file_path, config, session_factory)
                    if pack.deep_ai_analysis
                    else await _analyze_file_shallow(file_path)
                )
                row.extracted_metadata = json.dumps(extracted, default=str)
                row.ai_run_id = extracted.get("run_id")

                mag, score, source = await _match_to_magazine(db, extracted)
                if mag is not None:
                    row.matched_magazine_id = mag.id
                    row.match_score = score
                    row.match_source = source

                stats["analyzed"] += 1
                row.status = "analyzed"
                row.analyzed_at = datetime.now()
                await db.flush()

                # ── 5. Décision ──────────────────────────────────
                if pack.preview_before_import:
                    row.status = "pending_user"
                    stats["pending_user"] += 1
                elif mag is not None and (score or 0) >= MATCH_STRONG_THRESHOLD:
                    ok, issue_id, msg = await _import_file_to_magazine(
                        db, file_path, mag.id, config,
                    )
                    if ok:
                        row.status = "imported"
                        row.resolved_issue_id = issue_id
                        row.resolved_at = datetime.now()
                        row.user_action = "assign_existing"
                        row.user_action_magazine_id = mag.id
                        stats["auto_imported"] += 1
                    else:
                        row.status = "error"
                        row.error_message = msg or "Import failed"
                elif pack.auto_create_missing_magazines and extracted.get("title"):
                    placeholder = await _create_placeholder_magazine(
                        db, pack, extracted,
                    )
                    ok, issue_id, msg = await _import_file_to_magazine(
                        db, file_path, placeholder.id, config,
                    )
                    if ok:
                        row.status = "imported"
                        row.resolved_issue_id = issue_id
                        row.resolved_at = datetime.now()
                        row.user_action = "create_magazine"
                        row.user_action_magazine_id = placeholder.id
                        stats["auto_imported"] += 1
                        stats["placeholder_created"] += 1
                    else:
                        row.status = "error"
                        row.error_message = msg or "Import failed"
                else:
                    # Aucun match assez fort + pas d'auto-create → user tranche.
                    row.status = "pending_user"
                    if extracted.get("title"):
                        row.proposed_magazine_data = json.dumps({
                            "title": extracted.get("title"),
                            "issn": extracted.get("issn"),
                            "frequency": pack.default_new_magazine_frequency,
                        })
                    stats["pending_user"] += 1
                await db.flush()
            except Exception as exc:
                logger.exception("Pack dispatch analyse fichier %s a échoué", row.filename)
                row.status = "error"
                row.error_message = f"{type(exc).__name__}: {exc}"
                await db.flush()

        await db.commit()
        summary = (
            f"{stats['analyzed']} analysés · "
            f"{stats['auto_imported']} importés · "
            f"{stats['pending_user']} en attente"
        )
        await activity_service.mark_done(activity_id, hint=summary)
        return stats
    except Exception as exc:
        logger.exception("process_pack_download error")
        await activity_service.mark_error(activity_id, str(exc))
        raise


# ─── Résolution utilisateur ───────────────────────────────────────────


async def resolve_dispatch_file(
    db: AsyncSession,
    file_id: int,
    action: str,
    magazine_id: int | None,
    magazine_data: dict[str, Any] | None,
    config,
) -> PackDispatchFile:
    """Applique la décision de l'utilisateur sur un fichier pending_user.

    ``action`` :
      - ``assign_existing`` : rattache au magazine ``magazine_id``.
      - ``create_magazine`` : crée un magazine avec ``magazine_data``
        (title, frequency, root_folder_id, quality_profile_id — hérite
        du pack si absents) puis import.
      - ``ignore`` : marque le fichier ignoré, aucun import.
    """
    row = await db.get(PackDispatchFile, file_id)
    if row is None:
        raise ValueError(f"dispatch file {file_id} not found")
    if row.status in ("imported", "ignored"):
        raise ValueError(f"file already resolved (status={row.status})")

    if action == "ignore":
        row.status = "ignored"
        row.user_action = "ignore"
        row.resolved_at = datetime.now()
        await db.commit()
        return row

    pack = await db.get(Pack, row.pack_id)
    if pack is None:
        raise ValueError(f"pack {row.pack_id} not found (orphan dispatch row)")

    target_magazine_id: int | None = None
    if action == "assign_existing":
        if magazine_id is None:
            raise ValueError("magazine_id required for assign_existing")
        target_magazine_id = magazine_id
    elif action == "create_magazine":
        from app.services import magazine_service

        create_data = dict(magazine_data or {})
        create_data.setdefault("root_folder_id", pack.root_folder_id)
        create_data.setdefault("quality_profile_id", pack.quality_profile_id)
        create_data.setdefault("frequency", pack.default_new_magazine_frequency)
        create_data.setdefault("title", "Inconnu")
        # Cette création est user-driven donc PAS placeholder.
        create_data.setdefault("is_placeholder", False)
        new_mag = await magazine_service.create_magazine(db, create_data)
        target_magazine_id = new_mag.id
    else:
        raise ValueError(f"invalid action: {action}")

    file_path = Path(row.path)
    if not file_path.exists():
        row.status = "error"
        row.error_message = f"Fichier introuvable sur disque : {file_path}"
        await db.commit()
        raise FileNotFoundError(str(file_path))

    ok, issue_id, msg = await _import_file_to_magazine(
        db, file_path, target_magazine_id, config,
    )
    if not ok:
        row.status = "error"
        row.error_message = msg or "Import failed"
        await db.commit()
        raise RuntimeError(msg or "Import failed")

    row.status = "imported"
    row.user_action = action
    row.user_action_magazine_id = target_magazine_id
    row.resolved_issue_id = issue_id
    row.resolved_at = datetime.now()
    await db.commit()
    return row


async def reanalyze_dispatch_file(
    db: AsyncSession,
    file_id: int,
    config,
    session_factory,
) -> PackDispatchFile:
    """Relance l'analyse IA (deep) sur un fichier — utile quand l'utilisateur
    ajuste les zones de crop ou change de modèle."""
    row = await db.get(PackDispatchFile, file_id)
    if row is None:
        raise ValueError(f"dispatch file {file_id} not found")
    file_path = Path(row.path)
    if not file_path.exists():
        row.status = "error"
        row.error_message = f"Fichier introuvable sur disque : {file_path}"
        await db.commit()
        return row

    extracted = await _analyze_file_deep(file_path, config, session_factory)
    row.extracted_metadata = json.dumps(extracted, default=str)
    row.ai_run_id = extracted.get("run_id")
    mag, score, source = await _match_to_magazine(db, extracted)
    row.matched_magazine_id = mag.id if mag else None
    row.match_score = score
    row.match_source = source
    row.status = "analyzed" if mag is None else "pending_user"
    row.analyzed_at = datetime.now()
    await db.commit()
    return row


async def list_dispatch_files(
    db: AsyncSession,
    pack_id: int,
    status: str | None = None,
) -> list[PackDispatchFile]:
    stmt = select(PackDispatchFile).where(PackDispatchFile.pack_id == pack_id)
    if status:
        stmt = stmt.where(PackDispatchFile.status == status)
    stmt = stmt.order_by(PackDispatchFile.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def delete_dispatch_file(db: AsyncSession, file_id: int) -> bool:
    row = await db.get(PackDispatchFile, file_id)
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True
