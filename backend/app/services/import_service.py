"""Import pipeline and naming template system."""

import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Default naming template
DEFAULT_TEMPLATE = "{magazine_title}/{magazine_title} - {number} ({year}-{month:02d}-{day:02d}).{format}"

# Valid template variables (English canonical names)
TEMPLATE_VARIABLES = {
    "magazine_title": "Magazine title",
    "number": "Issue number",
    "volume": "Volume number",
    "year": "Publication year",
    "month": "Publication month (01-12)",
    "day": "Publication day (01-31)",
    "quality": "File quality (truepdf, retail, etc.)",
    "format": "File format (pdf, epub, etc.)",
    "group": "Release group name",
    "language": "Language code",
    "special": "Special/Hors-Série indicator (HS if special, empty otherwise)",
}

# French aliases → canonical English name
_FRENCH_ALIASES = {
    "titre_magazine": "magazine_title",
    "titre": "magazine_title",
    "numero": "number",
    "annee": "year",
    "mois": "month",
    "jour": "day",
    "qualite": "quality",
    "groupe": "group",
    "langue": "language",
    "hors_serie": "special",
    "hs": "special",
}

# Characters not allowed in filenames
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def validate_template(template: str) -> tuple[bool, str]:
    """Validate a naming template. Returns (is_valid, error_message)."""
    if not template:
        return False, "Template cannot be empty"

    if INVALID_CHARS.search(template.replace("{", "").replace("}", "")):
        return False, "Template contains invalid filesystem characters"

    # Check all variables are recognized (English or French)
    found_vars = re.findall(r"\{(\w+)(?::[^}]*)?\}", template)
    all_known = set(TEMPLATE_VARIABLES) | set(_FRENCH_ALIASES)
    for var in found_vars:
        if var not in all_known:
            return False, f"Unknown template variable: {{{var}}}"

    if not found_vars:
        return False, "Template must contain at least one variable"

    return True, ""


def apply_template(
    template: str,
    magazine_title: str = "",
    number: int | None = None,
    volume: int | None = None,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    quality: str = "unknown",
    file_format: str = "pdf",
    group: str | None = None,
    language: str = "unknown",
    is_special: bool = False,
) -> str:
    """Apply naming template with given values."""
    result = template

    # Coerce number/date fields — l'IA les renvoie parfois en string
    # (JSON parse, ou noms comme "Août" au lieu du numéro). On tolère
    # str-de-digits (fait le cast) et retombe sur "00"/"0000" pour tout
    # ce qui ne convertit pas.
    def _to_int(v: object) -> int | None:
        if v is None or v == "":
            return None
        if isinstance(v, int):
            return v
        try:
            return int(str(v).strip())
        except (ValueError, TypeError):
            return None

    year_i = _to_int(year)
    month_i = _to_int(month)
    day_i = _to_int(day)
    number_i = number if isinstance(number, int) else _to_int(number)

    values = {
        "magazine_title": _sanitize_filename(magazine_title) if magazine_title else "Unknown",
        "number": str(number_i) if number_i is not None else "000",
        "volume": str(volume) if volume is not None else "",
        "year": str(year_i) if year_i is not None else "0000",
        "month": f"{month_i:02d}" if month_i is not None else "00",
        "day": f"{day_i:02d}" if day_i is not None else "00",
        "quality": quality,
        "format": file_format.lower().lstrip("."),
        "group": group or "",
        "language": language,
        "special": "HS" if is_special else "",
    }

    # Build reverse alias map: french_name -> same value as the canonical english name
    alias_values = {alias: values[canonical] for alias, canonical in _FRENCH_ALIASES.items()}
    all_values = {**values, **alias_values}

    # Handle format specifiers like {month:02d}
    for var_name, value in all_values.items():
        # Simple replacement without format spec
        result = result.replace(f"{{{var_name}}}", value)
        # Also handle format specs by replacing them with the pre-formatted value
        result = re.sub(rf"\{{{var_name}:[^}}]*\}}", value, result)

    # Clean up empty segments
    result = re.sub(r"-00(?=\))", "", result)  # Remove -00 day suffix
    result = re.sub(r" +- +\(\d{4}-00\)", "", result)  # Remove date if no month
    result = re.sub(r"\(\s*\)", "", result)  # Remove empty parens
    result = re.sub(r" - HS", " HS", result)  # Normalize HS placement
    result = re.sub(r" {2,}", " ", result)  # Collapse multiple spaces
    result = result.strip()

    return result


def preview_template(template: str) -> str:
    """Generate a preview of the template with sample data."""
    return apply_template(
        template,
        magazine_title="Science et Vie",
        number=1285,
        volume=None,
        year=2025,
        month=3,
        day=15,
        quality="truepdf",
        file_format="pdf",
        group="TeamRelease",
        language="french",
    )


def _sanitize_filename(name: str) -> str:
    """Remove invalid filesystem characters from a filename part."""
    return INVALID_CHARS.sub("", name).strip()


async def extract_cover(pdf_path: str | Path, output_dir: str | Path) -> str | None:
    """Extract cover image from first page of PDF.
    Returns path to cover image or None on failure.
    """
    import asyncio

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cover_path = output_dir / f"{pdf_path.stem}.jpg"

    def _extract() -> str | None:
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(pdf_path))
            if len(doc) == 0:
                doc.close()
                return None

            page = doc[0]
            # Render at 2x for quality, then we get a good resolution
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)

            # Resize to max 500px wide
            if pix.width > 500:
                scale = 500 / pix.width
                mat = fitz.Matrix(scale * 2, scale * 2)
                pix = page.get_pixmap(matrix=mat)

            pix.save(str(cover_path))
            doc.close()
            return str(cover_path)
        except Exception:
            logger.warning("Failed to extract cover from %s", pdf_path, exc_info=True)
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract)


async def import_file(
    file_path: Path,
    library_path: Path,
    magazine_title: str,
    naming_template: str,
    number: int | None = None,
    volume: int | None = None,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    quality: str = "unknown",
    file_format: str = "pdf",
    group: str | None = None,
    language: str = "unknown",
    import_mode: str = "copy",
    is_special: bool = False,
) -> Path:
    """Import a file into the library using the naming template.

    import_mode controls how the source file is handled:
      - "copy": copy the file (source remains in download client)
      - "move": move the file (source is removed)
      - "copy_delete": copy then delete the source

    Returns the new file path.
    """
    new_name = apply_template(
        naming_template,
        magazine_title=magazine_title,
        number=number,
        volume=volume,
        year=year,
        month=month,
        day=day,
        quality=quality,
        file_format=file_format,
        group=group,
        language=language,
        is_special=is_special,
    )

    dest = library_path / new_name
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Check disk space
    usage = shutil.disk_usage(dest.parent)
    file_size = file_path.stat().st_size
    if usage.free < file_size * 1.1:  # 10% margin
        raise OSError(f"Insufficient disk space: {usage.free} free, need {file_size}")

    if import_mode == "move":
        shutil.move(str(file_path), str(dest))
        logger.info("Moved %s → %s", file_path.name, dest)
    elif import_mode == "copy_delete":
        shutil.copy2(str(file_path), str(dest))
        file_path.unlink()
        logger.info("Copied+deleted %s → %s", file_path.name, dest)
    else:
        # Default: copy
        shutil.copy2(str(file_path), str(dest))
        logger.info("Copied %s → %s", file_path.name, dest)

    return dest


async def process_downloaded_file(
    db,
    file_path: Path,
    config,
    magazine_id: int | None = None,
    issue_id: int | None = None,
    *,
    source_type: str = "torrent",
    source_pack_id: int | None = None,
    source_release_title: str | None = None,
) -> dict:
    """Full import pipeline: parse → match → rename → move → update DB → cover → notify.

    When issue_id is provided (e.g. from grab registry), the issue is loaded
    directly and both magazine fuzzy matching and issue number/date matching
    are skipped entirely.

    When only magazine_id is provided (e.g. from Manual Research), the fuzzy
    title matching step is skipped and the magazine is loaded directly by ID.

    Returns a dict with keys: success, issue_id, message.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.issue import Issue
    from app.models.issue_file import IssueFile
    from app.models.magazine import Magazine
    from app.models.root_folder import RootFolder
    from app.parser.magazine_parser import fuzzy_match_title, parse_magazine_filename
    from app.services.history_service import create_event
    from app.services.quality_service import should_upgrade

    supported = {".pdf", ".epub", ".cbr", ".cbz"}
    if file_path.suffix.lower() not in supported:
        await create_event(
            db, "error",
            magazine_id=magazine_id,
            issue_id=issue_id,
            details=f"Import failed: unsupported format {file_path.suffix}",
            data={
                "error": "unsupported_format",
                "filename": file_path.name,
                "format": file_path.suffix,
            },
        )
        return {"success": False, "issue_id": None, "message": "Unsupported file format"}

    # Activity tracking (queue visibility) — un item par import qui
    # accumule les steps AI + parse + copy + cover. Auto-cleanup 30 s
    # après complete.
    from app.services.import_activity_tracker import tracker as _act
    activity_id = f"import:{file_path.name}:{int(_time.time() * 1000)}" if False else file_path.name
    # Utilise le nom fichier comme id — évite les doublons pour le même
    # download re-triggé, et cohérent avec le download_id logique.
    import time as _time
    activity_id = f"{file_path.name}"
    _act.register(
        activity_id=activity_id,
        file_name=file_path.name,
        magazine_id=magazine_id,
        issue_id=issue_id,
    )
    _act.push_step(activity_id, "parse")

    # 1. Parse filename
    parsed = parse_magazine_filename(file_path.name)

    # 1b. AI enrichment (if enabled) — refines `parsed` fields based
    # on torrent name + PDF cover. Runs BEFORE rename/import so the
    # naming template + issue matching use the enriched values.
    # Never blocks : any failure logs a warning and keeps `parsed`
    # untouched, so the regex parser stays as ultimate fallback.
    if getattr(config, "ai_enrichment_enabled", False):
        try:
            from app.database import async_session_factory
            from app.services.ai_enrichment_service import (
                AIEnrichmentService,
                merge_ai_into_parsed,
            )

            trigger = (
                "import_manual"
                if magazine_id is not None or issue_id is not None
                else "grab_auto"
            )
            enrich_svc = AIEnrichmentService(config, async_session_factory)

            # Progress callback : mapping stage → step_id du tracker.
            # `stage` vient de AIEnrichmentService.enrich() : "text",
            # "vision", "switch", "arbiter", "cache", "skip", "done".
            def _ai_progress(stage: str, detail: str) -> None:
                _stage_map = {
                    "text": "ai_text",
                    "vision": "ai_vision",
                    "switch": (
                        "ai_switch_vision" if "vision" in detail.lower()
                        else "ai_switch_text"
                    ),
                    "arbiter": "ai_arbiter",
                    "skip": "ai_skipped",
                    "cache": "ai_cache_hit",  # résultat AI précédent réutilisé — pas un fallback
                }
                _act.push_step(
                    activity_id,
                    _stage_map.get(stage, f"ai_{stage}"),
                    hint=detail,
                )

            enrich_result = await enrich_svc.enrich(
                torrent_name=file_path.name,
                pdf_path=file_path,
                magazine_id=magazine_id,
                issue_id=issue_id,
                trigger=trigger,
                progress_cb=_ai_progress,
            )
            parsed = merge_ai_into_parsed(
                parsed, enrich_result.final, config.ai_enrichment_mode
            )
            logger.info(
                "AI enrichment run=%s mode=%s applied: %s",
                enrich_result.run_id,
                enrich_result.applied_mode,
                enrich_result.final,
            )
            # `propose` mode stores propositions in DB but doesn't
            # touch `parsed` — the operator validates via UI later.
            if (
                config.ai_enrichment_mode == "propose"
                and enrich_result.final
                and enrich_result.applied_mode == "propose"
            ):
                from app.models.ai_run import AIEnrichmentProposal

                proposal = AIEnrichmentProposal(
                    magazine_id=magazine_id,
                    issue_id=issue_id,
                    run_id=enrich_result.run_id,
                    proposed_json=str(enrich_result.final),
                    status="pending",
                )
                db.add(proposal)
                await db.flush()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AI enrichment failed (non-fatal, falling back to parser): %s",
                exc,
                exc_info=True,
            )

    # Fast path: when issue_id is known (from grab registry), load directly
    # and skip fuzzy title matching + issue number/date matching entirely
    if issue_id:
        issue_result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.file), selectinload(Issue.magazine))
            .where(Issue.id == issue_id)
        )
        issue = issue_result.scalars().first()
        if issue and issue.magazine:
            magazine = issue.magazine
            existing_file = issue.file
            logger.info(
                "Direct issue lookup: issue_id=%d → %s #%s",
                issue_id, magazine.title, issue.number,
            )
        else:
            logger.warning("issue_id=%d not found, falling back to filename parsing", issue_id)
            issue_id = None  # fall through to normal path

    if not issue_id:
        # 2. Resolve magazine — either by ID (fast path) or fuzzy match
        magazine = None
        if magazine_id:
            mag_result = await db.execute(
                select(Magazine).where(Magazine.id == magazine_id)
            )
            magazine = mag_result.scalars().first()
            if magazine:
                logger.info("Resolved magazine by ID: %s (id=%d)", magazine.title, magazine_id)

        if not magazine:
            # Need a parseable title for fuzzy matching
            if not parsed.title:
                logger.warning("Could not parse title from %s", file_path.name)
                _act.mark_error(activity_id, "Nom de fichier illisible")
                return {"success": False, "issue_id": None, "message": "Unparseable filename"}

            _act.push_step(activity_id, "match")
            mag_result = await db.execute(select(Magazine))
            magazines = mag_result.scalars().all()
            known_titles = [m.title for m in magazines]

            match = fuzzy_match_title(parsed.title, known_titles, threshold=80.0)
            if not match:
                # Move to unmatched directory
                unmatched_dir = (
                    Path(config.download_path) / "unmatched"
                    if hasattr(config, "download_path")
                    else file_path.parent / "unmatched"
                )
                unmatched_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(unmatched_dir / file_path.name))
                await create_event(
                    db, "unmatched",
                    details=f"Unmatched file: {file_path.name}",
                    data={
                        "filename": file_path.name,
                        "parsed_title": parsed.title,
                        "source_path": str(file_path),
                    },
                )
                _act.mark_error(activity_id, f"Aucun magazine ne correspond à « {parsed.title} »")
                return {"success": False, "issue_id": None, "message": f"No matching magazine for '{parsed.title}'"}

            matched_title, match_score = match
            magazine = next(m for m in magazines if m.title == matched_title)

        # 3. Match issue by number or date
        issue = None
        if parsed.number is not None:
            issue_result = await db.execute(
                select(Issue)
                .options(selectinload(Issue.file))
                .where(Issue.magazine_id == magazine.id, Issue.number == parsed.number)
            )
            issue = issue_result.scalars().first()

        # Frequency-aware date matching:
        # - daily/weekly/biweekly → exact day match
        # - monthly and above → month+year only (ignore day)
        # - quarterly → same quarter+year
        freq = getattr(magazine, "frequency", "monthly")
        day_precise = freq in ("daily", "weekly", "biweekly")

        if not issue and parsed.year and parsed.month:
            if day_precise and parsed.day:
                # Day-precise matching (for daily/weekly publications)
                issue_result = await db.execute(
                    select(Issue)
                    .options(selectinload(Issue.file))
                    .where(
                        Issue.magazine_id == magazine.id,
                        Issue.year == parsed.year,
                        Issue.month == parsed.month,
                        Issue.day == parsed.day,
                    )
                )
                issue = issue_result.scalars().first()

            if not issue and freq in ("quarterly", "semiannual", "annual"):
                # Quarter/semester/year-level matching
                from app.services.calendar_service import FREQUENCY_DELTAS

                period_months = FREQUENCY_DELTAS.get(freq, 1)
                if isinstance(period_months, int) and period_months > 1:
                    # Find issues in the same period window
                    period_start_month = ((parsed.month - 1) // period_months) * period_months + 1
                    months_in_period = list(range(period_start_month, period_start_month + period_months))
                    issue_result = await db.execute(
                        select(Issue)
                        .options(selectinload(Issue.file))
                        .where(
                            Issue.magazine_id == magazine.id,
                            Issue.year == parsed.year,
                            Issue.month.in_(months_in_period),
                        )
                    )
                    issue = issue_result.scalars().first()

            if not issue and not day_precise:
                # Month-level matching réservé aux fréquences monthly+.
                # Sur un quotidien / hebdo / bimensuel deux fichiers du
                # même mois sont des issues DIFFÉRENTES — le fallback
                # month+year les collapsait en un seul issue et le
                # nouveau se voyait refusé "Not a quality upgrade"
                # (comparaison contre l'issue précédent du mois).
                # Pour ces fréquences : si le day-precise match n'a rien
                # trouvé, c'est un NOUVEL issue à créer, pas un doublon.
                issue_result = await db.execute(
                    select(Issue)
                    .options(selectinload(Issue.file))
                    .where(
                        Issue.magazine_id == magazine.id,
                        Issue.year == parsed.year,
                        Issue.month == parsed.month,
                    )
                )
                issue = issue_result.scalars().first()

        # Save eagerly-loaded file reference before potentially creating a new issue
        # (avoids lazy-load MissingGreenlet errors in background tasks)
        existing_file = None if issue is None else issue.file

        if not issue:
            # Remove any forecast with the same number to avoid unique constraint violation
            if parsed.number is not None:
                forecast_result = await db.execute(
                    select(Issue).where(
                        Issue.magazine_id == magazine.id,
                        Issue.number == parsed.number,
                        Issue.is_forecast == True,  # noqa: E712
                    )
                )
                for forecast in forecast_result.scalars().all():
                    await db.delete(forecast)
                await db.flush()

            # Create a new issue for this file — coerce défensif au
            # cas où parsed contient encore un ancien objet non-fixé
            # (ceinture-bretelles avec merge_ai_into_parsed qui coerce
            # déjà au boundary IA). SQLite ne vérifie pas les types
            # de colonnes → une string stockée dans un Integer casse
            # tous les filtres numériques + le filename template.
            from app.services.ai_enrichment_service import _coerce_int_or_none
            issue = Issue(
                magazine_id=magazine.id,
                number=_coerce_int_or_none(parsed.number),
                year=_coerce_int_or_none(parsed.year),
                month=_coerce_int_or_none(parsed.month),
                day=_coerce_int_or_none(parsed.day),
                title=(getattr(parsed, "title", None) or None) if not isinstance(getattr(parsed, "title", None), str) or not getattr(parsed, "title", "").strip() else parsed.title.strip(),
                subtitle=getattr(parsed, "subtitle", None),
                price=getattr(parsed, "price", None),
                issn=getattr(parsed, "issn", None),
                is_special=bool(parsed.is_special),
                status="available",
                monitored=True,
            )
            db.add(issue)
            await db.flush()

    # 4. Check quality upgrade
    if existing_file:
        if magazine.quality_profile_id:
            from app.services.quality_service import get_profile

            profile = await get_profile(db, magazine.quality_profile_id)
            if profile and not should_upgrade(existing_file.quality, parsed.quality, profile):
                logger.info(
                    "Skipping %s — quality %s not an upgrade over %s",
                    file_path.name, parsed.quality, existing_file.quality,
                )
                # Marque le tracker comme terminé (état neutre, pas une
                # erreur) pour que la queue affiche « Déjà importé »
                # au lieu de rester bloqué en « IMPORTING » 30 s+.
                _act.push_step(
                    activity_id,
                    "skipped_no_upgrade",
                    hint=f"qualité {parsed.quality or 'inconnue'} ≤ existante ({existing_file.quality or 'inconnue'})",
                )
                _act.mark_done(activity_id, hint="Déjà importé — pas de gain qualité")
                return {"success": False, "issue_id": issue.id, "message": "Not a quality upgrade"}

        # Remove old file
        old_path = Path(existing_file.path)
        if old_path.exists():
            old_path.unlink()
        await db.delete(existing_file)
        await db.flush()

    # 5. Get library path from root folder
    rf_result = await db.execute(
        select(RootFolder).where(RootFolder.id == magazine.root_folder_id)
    )
    root_folder = rf_result.scalars().first()
    library_path = Path(root_folder.path) if root_folder else Path("/magazines")

    _act.push_step(activity_id, "copy")
    # 6. Apply naming template and move file
    # Prefer issue DB values over parsed filename values (the download
    # filename often lacks the issue number that forecasts already know)
    naming_template = getattr(config, "naming_template", DEFAULT_TEMPLATE)

    eff_number = issue.number if issue.number is not None else parsed.number
    eff_volume = issue.volume if getattr(issue, "volume", None) is not None else parsed.volume
    eff_year = issue.year if issue.year is not None else parsed.year
    eff_month = issue.month if issue.month is not None else parsed.month
    eff_day = issue.day if issue.day is not None else parsed.day

    import_mode = getattr(config, "import_mode", "copy")
    try:
        dest = await import_file(
            file_path=file_path,
            library_path=library_path,
            magazine_title=magazine.title,
            naming_template=naming_template,
            number=eff_number,
            volume=eff_volume,
            year=eff_year,
            month=eff_month,
            day=eff_day,
            quality=parsed.quality,
            file_format=parsed.format,
            group=parsed.release_group,
            language=parsed.language,
            import_mode=import_mode,
            is_special=getattr(issue, "is_special", False),
        )
    except OSError as e:
        await create_event(
            db, "error",
            magazine_id=magazine.id,
            issue_id=issue.id,
            details=f"Import failed: {e}",
            data={
                "error": str(e),
                "source_path": str(file_path),
                "magazine_title": magazine.title,
            },
        )
        _act.mark_error(activity_id, str(e))
        return {"success": False, "issue_id": issue.id, "message": str(e)}

    # 7. If another issue already owns a file at the same path, deduplicate
    #    by appending a numeric suffix (never steal another issue's file).
    existing_at_path = await db.execute(
        select(IssueFile).where(IssueFile.path == str(dest))
    )
    conflicting = existing_at_path.scalars().first()
    if conflicting and conflicting.issue_id != issue.id:
        # Rename the new file to avoid collision
        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent
        counter = 2
        while True:
            candidate = parent / f"{stem} ({counter}){suffix}"
            check = await db.execute(
                select(IssueFile).where(IssueFile.path == str(candidate))
            )
            if not check.scalars().first() and not candidate.exists():
                break
            counter += 1
        dest.rename(candidate)
        dest = candidate
        logger.info("Deduplicated file path: %s", dest)
    elif conflicting and conflicting.issue_id == issue.id:
        # Same issue re-import (upgrade path already handled above)
        await db.delete(conflicting)
        await db.flush()

    # 8. Create IssueFile record
    issue_file = IssueFile(
        issue_id=issue.id,
        magazine_id=issue.magazine_id,
        path=str(dest),
        relative_path=str(dest.relative_to(library_path)),
        size=dest.stat().st_size,
        format=parsed.format,
        quality=parsed.quality,
        original_filename=file_path.name,
        release_group=parsed.release_group,
        language=parsed.language if parsed.language != "unknown" else None,
        source_type=source_type,
        source_pack_id=source_pack_id,
        source_release_title=source_release_title,
    )
    db.add(issue_file)

    # 9. Update issue status
    issue.status = "available"
    await db.flush()

    _act.push_step(activity_id, "cover")
    # 10. Extract cover
    covers_dir = Path(getattr(config, "config_path", "/config")).parent / "covers"
    cover = await extract_cover(dest, covers_dir)
    if cover:
        issue.cover_path = cover
        # Use as magazine cover if magazine has none or auto-mode is on
        if not magazine.cover_path or magazine.use_latest_issue_cover:
            magazine.cover_path = cover
            logger.info("Set magazine cover from imported issue: %s", cover)
        await db.flush()

    _act.push_step(activity_id, "notify")
    # 11. Create history event
    event_type = "upgrade" if existing_file else "import"
    await create_event(
        db, event_type,
        magazine_id=magazine.id,
        issue_id=issue.id,
        details=f"Imported: {dest.name} ({parsed.quality})",
        data={
            "source_path": str(file_path),
            "dest_path": str(dest),
            "filename": dest.name,
            "quality": parsed.quality,
            "format": parsed.format,
            "magazine_title": magazine.title,
            "issue_number": issue.number,
            "release_group": parsed.release_group,
            "import_mode": import_mode,
        },
    )

    # 12. Dispatch notifications
    try:
        from app.notifications.base import NotificationPayload
        from app.services.notification_service import dispatch
        payload = NotificationPayload(
            event_type=event_type,
            magazine_title=magazine.title,
            issue_number=parsed.number,
            quality=parsed.quality,
            cover_url=f"/api/v1/issue/{issue.id}/cover" if cover else None,
        )
        await dispatch(db, event_type, payload)
    except Exception:
        logger.warning("Notification dispatch failed", exc_info=True)

    # 13. Reconcile forecast
    try:
        from app.services.calendar_service import reconcile_forecast
        await reconcile_forecast(db, issue)
    except Exception:
        logger.debug("Forecast reconciliation skipped", exc_info=True)

    _act.mark_done(activity_id, hint=dest.name)
    return {"success": True, "issue_id": issue.id, "message": f"Imported to {dest}"}


async def import_file_for_issue(
    db,
    file_path: Path,
    issue_id: int,
    config,
) -> dict:
    """Import a downloaded file directly for a known issue (skips filename parsing).

    Used by IA/AA downloads where the issue is already known.
    Returns a dict with keys: success, issue_id, message.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.issue import Issue
    from app.models.issue_file import IssueFile
    from app.models.magazine import Magazine
    from app.models.root_folder import RootFolder
    from app.services.history_service import create_event

    supported = {".pdf", ".epub", ".cbr", ".cbz"}
    if file_path.suffix.lower() not in supported:
        return {
            "success": False,
            "issue_id": issue_id,
            "message": "Unsupported file format",
        }

    # 1. Load issue with its magazine
    issue_result = await db.execute(
        select(Issue)
        .options(selectinload(Issue.file))
        .where(Issue.id == issue_id)
    )
    issue = issue_result.scalars().first()
    if not issue:
        return {
            "success": False,
            "issue_id": issue_id,
            "message": f"Issue {issue_id} not found",
        }

    mag_result = await db.execute(
        select(Magazine).where(Magazine.id == issue.magazine_id)
    )
    magazine = mag_result.scalars().first()
    if not magazine:
        return {
            "success": False,
            "issue_id": issue_id,
            "message": "Magazine not found",
        }

    # 2. If issue already has a file, replace it
    if issue.file:
        old_path = Path(issue.file.path)
        if old_path.exists():
            old_path.unlink()
        await db.delete(issue.file)
        await db.flush()

    # 3. Get library path
    rf_result = await db.execute(
        select(RootFolder).where(
            RootFolder.id == magazine.root_folder_id
        )
    )
    root_folder = rf_result.scalars().first()
    library_path = (
        Path(root_folder.path) if root_folder else Path("/magazines")
    )

    # 4. Determine file format from extension
    file_format = file_path.suffix.lstrip(".").lower() or "pdf"

    # 5. Apply naming template and import file
    naming_template = getattr(
        config, "naming_template", DEFAULT_TEMPLATE
    )
    import_mode = getattr(config, "import_mode", "copy")
    try:
        dest = await import_file(
            file_path=file_path,
            library_path=library_path,
            magazine_title=magazine.title,
            naming_template=naming_template,
            number=issue.number,
            year=issue.year,
            month=issue.month,
            day=issue.day,
            quality="unknown",
            file_format=file_format,
            import_mode=import_mode,
        )
    except OSError as e:
        await create_event(
            db, "error",
            magazine_id=magazine.id,
            issue_id=issue.id,
            details=f"Import failed: {e}",
            data={
                "error": str(e),
                "source_path": str(file_path),
                "magazine_title": magazine.title,
            },
        )
        return {
            "success": False,
            "issue_id": issue.id,
            "message": str(e),
        }

    # 6. If another issue already owns a file at the same path, deduplicate
    existing_at_path = await db.execute(
        select(IssueFile).where(IssueFile.path == str(dest))
    )
    conflicting = existing_at_path.scalars().first()
    if conflicting and conflicting.issue_id != issue.id:
        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent
        counter = 2
        while True:
            candidate = parent / f"{stem} ({counter}){suffix}"
            check = await db.execute(
                select(IssueFile).where(IssueFile.path == str(candidate))
            )
            if not check.scalars().first() and not candidate.exists():
                break
            counter += 1
        dest.rename(candidate)
        dest = candidate
        logger.info("Deduplicated file path: %s", dest)
    elif conflicting and conflicting.issue_id == issue.id:
        await db.delete(conflicting)
        await db.flush()

    # 7. Create IssueFile record — source_type par défaut torrent
    # (utilisé par le scene importer + reimport manuel).
    issue_file = IssueFile(
        issue_id=issue.id,
        magazine_id=issue.magazine_id,
        path=str(dest),
        relative_path=str(dest.relative_to(library_path)),
        size=dest.stat().st_size,
        format=file_format,
        quality="unknown",
        original_filename=file_path.name,
    )
    db.add(issue_file)

    # 8. Update issue status
    issue.status = "available"
    await db.flush()

    # 9. Extract cover
    covers_dir = (
        Path(getattr(config, "config_path", "/config")).parent / "covers"
    )
    cover = await extract_cover(dest, covers_dir)
    if cover:
        issue.cover_path = cover
        # Use as magazine cover if magazine has none or auto-mode is on
        if not magazine.cover_path or magazine.use_latest_issue_cover:
            magazine.cover_path = cover
            logger.info("Set magazine cover from imported issue: %s", cover)
        await db.flush()

    # 10. Create history event
    await create_event(
        db, "import",
        magazine_id=magazine.id,
        issue_id=issue.id,
        details=f"Imported: {dest.name}",
        data={
            "source_path": str(file_path),
            "dest_path": str(dest),
            "filename": dest.name,
            "format": file_format,
            "magazine_title": magazine.title,
            "issue_number": issue.number,
            "import_mode": import_mode,
        },
    )

    # 11. Dispatch notifications
    try:
        from app.notifications.base import NotificationPayload
        from app.services.notification_service import dispatch
        payload = NotificationPayload(
            event_type="import",
            magazine_title=magazine.title,
            issue_number=issue.number,
            quality="unknown",
            cover_url=(
                f"/api/v1/issue/{issue.id}/cover" if cover
                else None
            ),
        )
        await dispatch(db, "import", payload)
    except Exception:
        logger.warning("Notification dispatch failed", exc_info=True)

    # 12. Reconcile forecast
    try:
        from app.services.calendar_service import reconcile_forecast
        await reconcile_forecast(db, issue)
    except Exception:
        logger.debug("Forecast reconciliation skipped", exc_info=True)

    return {
        "success": True,
        "issue_id": issue.id,
        "message": f"Imported to {dest}",
    }
