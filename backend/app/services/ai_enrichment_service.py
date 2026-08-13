"""AI metadata enrichment pipeline for magazines.

Sequential pipeline (per the user requirement — no parallelism so
the queue shows a clean step-by-step trace) :

    0. cache check              (skip if hit)
    1. text LLM                 (torrent name → JSON)
    2. switch model             (unload text, load vision)
    3. vision LLM × N pages     (cover, back, ...)
    4. switch model             (unload vision, load arbiter = text)
    5. arbiter LLM              (merge torrent + vision → final JSON)
    6. write result             (mode-dependent : replace/complete/propose)

Each stage emits a progress event via ``progress_cb(stage, detail)``
so the caller (import service, reanalyze endpoint) can push it to
the queue UI.

Fallback rule : any Ollama step that fails (model missing, network
error, invalid JSON output) is logged and the pipeline skips
gracefully to the caller's native parser. It NEVER raises out —
enrichment is optional value-add, not a blocker for import.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.services.ai_ollama_adapter import (
    OllamaAdapter,
    OllamaError,
    encode_image_file,
)

logger = logging.getLogger(__name__)


ProgressCb = Callable[[str, str], None]


@dataclass
class EnrichmentResult:
    """Return value of ``enrich()`` — safe to consume regardless of mode.

    ``final`` is the merged fields (may be empty dict if pipeline
    fell back). ``applied_mode`` describes what was actually done :
    ``remplace`` / ``complete`` / ``propose`` / ``skipped_fallback``.
    ``run_id`` is the id of the ``AIEnrichmentRun`` row created for
    this execution — the caller may link the row to its own job.
    """

    final: dict[str, Any]
    applied_mode: str
    run_id: int
    steps: list[dict[str, Any]] = field(default_factory=list)
    total_elapsed_ms: int = 0


def _arbitrate(
    torrent: dict[str, Any],
    vision_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge torrent (primary) + vision outputs (fill nulls only).

    Rule set — strict, deterministic, no LLM :
      - Chaque champ du torrent non-null gagne, PÉRIODE. On ne remplace
        jamais une valeur torrent par une valeur vision (évite les
        hallucinations vision de venir polluer un torrent bien parsé).
      - Si `title` est null côté torrent → prend le title vision.
      - Pour issue_number/date : on scanne le `raw_text` retourné par
        la vision (mode OCR brut) avec des regex robustes qui
        distinguent le N° d'édition (« N° 26 290 ») du prix (« 2,70 € »)
        et de l'année de publication (« 81ᵉ année »).
      - Le pipeline supporte encore les anciens outputs vision
        (`title`/`issue_number`/`date_text` structurés) pour compat.
    """
    out: dict[str, Any] = {
        "title": torrent.get("title"),
        "issue_number": torrent.get("issue_number"),
        "year": torrent.get("year"),
        "month": torrent.get("month"),
        "day": torrent.get("day"),
        "is_hs": bool(torrent.get("is_hs")),
        "series_number": torrent.get("series_number"),
    }

    for entry in vision_outputs:
        vd = entry.get("data") if isinstance(entry, dict) else {}
        if not isinstance(vd, dict):
            continue

        # Title : le vision `title` structuré si présent + non pollué
        # (contient pas de "€" ou chiffre isolé qui trahit une erreur
        # de catégorisation).
        if out["title"] is None:
            vt = vd.get("title")
            if isinstance(vt, str) and vt.strip():
                stripped = vt.strip()
                # Filtre : si le "title" contient un symbole prix ou
                # commence par un chiffre, c'est un faux positif —
                # cherche dans raw_text un vrai titre à la place.
                if "€" not in stripped and not stripped[:1].isdigit():
                    out["title"] = _normalise_title(stripped)

        # Aggregate all string blobs into `text_pool` for smart parsing.
        text_pool = " ".join(
            str(v) for v in [
                vd.get("raw_text"),
                vd.get("date_text"),
                vd.get("title"),
            ] if v
        )
        if not text_pool:
            continue

        # issue_number : cherche « N° XXXXX », « No XXXXX », « # XXXXX »
        # (avec ou sans espace au milieu, 3-6 chiffres au total).
        # Évite « 80 ans », « 81ᵉ année », « 2,70 € », « 100 pages ».
        if out["issue_number"] is None:
            parsed_num = _extract_issue_number(text_pool)
            if parsed_num is not None:
                out["issue_number"] = parsed_num

        # Date : cherche des formats courants FR dans tout le raw_text.
        # `_parse_french_date` gère « lundi 10 août 2026 »,
        # « Mars 2024 », « 2016-4-23 », « 12/08/2026 ».
        if not all(out.get(k) is not None for k in ("year", "month", "day")):
            y, m, d = _parse_french_date(text_pool)
            if y and out.get("year") is None:
                out["year"] = y
            if m and out.get("month") is None:
                out["month"] = m
            if d and out.get("day") is None:
                out["day"] = d

    # Confidence : ratio de champs non-null pondéré.
    core_fields = ["title", "issue_number", "year", "month", "day"]
    non_null = sum(1 for f in core_fields if out.get(f) is not None)
    out["confidence"] = round(non_null / len(core_fields), 2)
    return out


def _build_arbiter_prompt(
    *,
    torrent: dict[str, Any],
    vision_outputs: list[dict[str, Any]],
    python_candidates: dict[str, Any],
    base_prompt: str,
) -> str:
    """Construit le prompt de l'arbitre IA final.

    Le prompt liste les 3 sources et demande à l'IA de choisir la valeur
    la plus RÉALISTE par champ, avec des règles explicites :
      - torrent = source primaire (fiabilité haute)
      - vision raw_text = OCR brut (pas d'interprétation)
      - python candidates = extraction regex (rapide mais peut manquer)

    Le raw_text vision (mélange titre, prix, dates, N°, mentions
    légales) est passé tel quel — l'IA doit trier.
    """
    # Concat des raw_text vision en un seul blob lisible.
    vision_dump = []
    for entry in vision_outputs:
        vd = entry.get("data") or {}
        if not isinstance(vd, dict):
            continue
        chunks = []
        for k in ("title", "raw_text", "date_text", "issue_number"):
            v = vd.get(k)
            if v not in (None, "", []):
                chunks.append(f"{k}={v!r}")
        if chunks:
            page = entry.get("page", "?")
            zone = entry.get("zone", "?")
            vision_dump.append(f"[page {page} · zone {zone}] " + " | ".join(chunks))
    vision_str = "\n".join(vision_dump) if vision_dump else "(aucune sortie vision)"

    return (
        f"{base_prompt}\n\n---\n"
        "Trois sources sont disponibles pour extraire les métadonnées "
        "de ce magazine. Choisis la valeur la plus RÉALISTE par champ.\n\n"
        f"### Source 1 — Analyse du nom torrent (fiable, source primaire)\n"
        f"{json.dumps(torrent, ensure_ascii=False, indent=2)}\n\n"
        f"### Source 2 — OCR brut de la couverture (à trier)\n"
        f"{vision_str}\n\n"
        f"### Source 3 — Candidats extraits par regex (rapide mais imparfait)\n"
        f"{json.dumps(python_candidates, ensure_ascii=False, indent=2)}\n\n"
        "### Règles de décision\n"
        "1. Si la source 1 (torrent) a une valeur NON-NULL, garde-la — "
        "elle est toujours prioritaire.\n"
        "2. Sinon, préfère la source 3 (Python) car elle a déjà filtré "
        "les faux positifs comme « 2,70 € » (prix), « 81ᵉ année » "
        "(année d'existence du magazine), « 80 ans ».\n"
        "3. Utilise la source 2 (OCR brut) comme vérification : lit le "
        "raw_text et repère les indices type « N° 26 290 », « lundi 10 "
        "août 2026 ». Si Python a raté un N° visible, extrais-le.\n"
        "4. Le N° d'édition est un ENTIER SANS espace (« 26 290 » → 26290). "
        "N'invente PAS un N° si tu n'en vois pas dans les 3 sources.\n"
        "5. La date doit être cohérente : year + month + day quand possible. "
        "Ignore les années < 1900 ou > 2100.\n\n"
        "Réponds avec un objet JSON strict :\n"
        "{\"title\": str|null, \"issue_number\": int|null, "
        "\"year\": int|null, \"month\": int|null, \"day\": int|null, "
        "\"is_hs\": bool, \"series_number\": int|null, "
        "\"confidence\": float}\n\n"
        "`confidence` entre 0 et 1 = estimation globale de fiabilité."
    )


def _postvalidate_arbiter(
    *,
    llm_out: dict[str, Any],
    torrent: dict[str, Any],
    python_candidates: dict[str, Any],
) -> dict[str, Any]:
    """Contrainte post-LLM : garantit la règle « torrent primaire ».

    Si l'arbitre IA a proposé une valeur qui contredit le torrent
    (torrent avait une valeur non-null et LLM en met une autre), on
    force le retour à la valeur torrent. Ça évite l'hallucination
    LLM qui écrase un torrent bien parsé (bug historique year=2016
    vision remplaçant year=2026 torrent).

    Pour issue_number : on accepte la valeur LLM SEULEMENT si elle
    figure aussi dans vision raw_text ou python candidates (pas
    d'invention pure).
    """
    out = dict(llm_out)  # copy

    for field in ("title", "issue_number", "year", "month", "day"):
        torrent_val = torrent.get(field)
        if torrent_val is not None and torrent_val != "":
            # Torrent gagne, toujours.
            out[field] = torrent_val

    # is_hs / series_number : garde torrent si dispo.
    if torrent.get("is_hs") is not None:
        out["is_hs"] = bool(torrent["is_hs"])
    else:
        out["is_hs"] = bool(out.get("is_hs"))

    if torrent.get("series_number") is not None:
        out["series_number"] = torrent["series_number"]

    # Anti-hallucination issue_number : si le LLM propose un N° absent
    # du torrent ET absent des python candidates → refuser sauf si
    # confidence >= 0.9 (le LLM a réellement vu un truc explicit).
    if (
        out.get("issue_number") is not None
        and torrent.get("issue_number") is None
        and python_candidates.get("issue_number") is None
    ):
        conf = float(out.get("confidence") or 0.0)
        if conf < 0.9:
            out["issue_number"] = None

    return out


def _extract_issue_number(text: str) -> int | None:
    """Extrait le numéro d'édition d'un blob texte.

    Cherche des patterns « N°/No/# XXXXX » (avec espace optionnel au
    milieu du nombre). Distingue des faux positifs :
      - « 81ᵉ année », « 80 ans » (année d'existence du magazine)
      - « 2,70 € », « 100 pages », « Rue de X 75001 »
      - dates ISO (« 2026-08-10 »)

    Renvoie l'entier ou None.
    """
    import re

    # Priorité 1 : préfixe explicite « N° » ou « No » ou « # » ou « nº ».
    # Autorise un espace au milieu du nombre (« N° 26 290 »).
    m = re.search(
        r"(?:n[°º]|no|#|numéro)\s*(\d{2,3}(?:\s?\d{2,3})*)",
        text,
        re.IGNORECASE,
    )
    if m:
        digits = m.group(1).replace(" ", "")
        try:
            return int(digits)
        except ValueError:
            pass

    # Priorité 2 : un nombre à 4-6 chiffres CONSÉCUTIFS qui n'est ni
    # une année (1900-2100) ni suivi de « ans/année/pages/€/€ ».
    for cand in re.finditer(r"\b(\d{4,6})\b", text):
        n = int(cand.group(1))
        # Filtre années
        if 1900 <= n <= 2100:
            continue
        # Filtre unités qui viennent après
        after = text[cand.end():cand.end() + 30].lower()
        if any(k in after[:15] for k in ("ans", "année", "pages", "€", "eur")):
            continue
        return n

    return None


_MONTHS_FR = {
    "janvier": 1, "jan": 1,
    "février": 2, "fevrier": 2, "fev": 2, "févr": 2,
    "mars": 3, "mar": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "août": 8, "aout": 8,
    "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "décembre": 12, "decembre": 12, "dec": 12, "déc": 12,
}


def _parse_french_date(text: str) -> tuple[int | None, int | None, int | None]:
    """Best-effort parse d'une date FR — accepte plusieurs formats :

    - « lundi 10 août 2026 »  → (2026, 8, 10)
    - « 15 janvier 2025 »     → (2025, 1, 15)
    - « Mars 2024 »           → (2024, 3, None)
    - « 2016-04-23 »          → (2016, 4, 23)
    - « 2016-4-23 »           → (2016, 4, 23)
    - « 12/08/2026 »          → (2026, 8, 12)

    Renvoie (year, month, day) avec des None quand introuvable.
    Jamais raise — sortie tuple(None, None, None) en cas d'échec.
    """
    if not text:
        return None, None, None
    import re
    txt = text.lower().strip()

    # ISO-like : YYYY-M-D
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", txt)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return y, mo, d

    # DD/MM/YYYY
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", txt)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return y, mo, d

    # « [DD] MONTHNAME YYYY »
    year_m = re.search(r"\b(19\d{2}|20\d{2})\b", txt)
    year = int(year_m.group(1)) if year_m else None
    month = None
    for name, num in _MONTHS_FR.items():
        if name in txt:
            month = num
            break
    day_m = re.search(r"\b(\d{1,2})\b", txt)
    day = int(day_m.group(1)) if day_m and 1 <= int(day_m.group(1)) <= 31 else None

    # Guard : si le jour "match" est en fait l'année tronquée, ignore.
    if day and year and day == year % 100:
        day = None
    return year, month, day


def _normalise_title(raw: str) -> str:
    """Normalise a vision-extracted title.

    Vision LLMs souvent renvoient en MAJUSCULES (`L'ÉQUIPE`). Le
    matcher fuzzy est case-insensitive donc pas critique, mais pour
    l'affichage on préfère `L'Équipe` façon éditeur.
    """
    stripped = raw.strip()
    if not stripped:
        return stripped
    # Si TOUT en majuscules → title case avec conservation apostrophes/accents
    if stripped == stripped.upper():
        # `L'ÉQUIPE` → `L'Équipe` : capitalize chaque « mot » séparé par
        # apostrophes ou espaces.
        parts = []
        buf = ""
        for ch in stripped:
            if ch in " '-":
                if buf:
                    parts.append(buf[0] + buf[1:].lower())
                    buf = ""
                parts.append(ch)
            else:
                buf += ch
        if buf:
            parts.append(buf[0] + buf[1:].lower())
        return "".join(parts)
    return stripped


def pdf_hash(pdf_path: Path | None) -> str:
    """SHA-256 of the PDF binary, or empty string when no file.

    Combined with magazine_id, this is the cache key. Any byte change
    in the file → cache miss → full re-run. Cheap on typical
    magazine sizes (~10-50 MB, sub-second on any SSD).
    """
    if pdf_path is None or not pdf_path.exists():
        return ""
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _render_page_pngs(
    pdf_path: Path,
    page_index_1based: int,
    dpi: int = 200,
    crop_mode: str = "full",
    custom_rect: dict[str, float] | None = None,
) -> list[tuple[str, bytes]]:
    """Render a PDF page → 1 or 2 PNGs selon ``crop_mode``.

    Retour : liste de ``(label, png_bytes)``. Labels :
      - ``"full"``   : la page entière
      - ``"top"``    : les 45 % supérieurs
      - ``"bottom"`` : les 45 % inférieurs
      - ``"custom"`` : rectangle défini par ``custom_rect``

    ``custom_rect`` : si fourni (dict avec ``x``, ``y``, ``w``, ``h`` en
    ratios 0..1), l'emporte sur ``crop_mode``. Utilisé quand l'user a
    dessiné visuellement une zone dans le UI Refresh IA — persisté sur
    Magazine.ai_crop_rect.

    ``crop_mode`` (utilisé UNIQUEMENT si custom_rect est None) :
      - ``"full"``      → [("full", ...)]
      - ``"top"``       → [("top", ...)]  ← quotidiens FR
      - ``"bottom"``    → [("bottom", ...)]  ← rare
      - ``"top_bottom"``→ [("top",...), ("bottom",...)]  ← robuste

    ``dpi`` : 200 = sweet spot minicpm-v:8b dans 8 Go VRAM.
    Raises IndexError when the page doesn't exist.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    try:
        n = doc.page_count
        if page_index_1based < 0:
            idx0 = n + page_index_1based
        else:
            idx0 = page_index_1based - 1
        if idx0 < 0 or idx0 >= n:
            raise IndexError(
                f"Page {page_index_1based} out of range (PDF has {n} pages)"
            )
        page = doc.load_page(idx0)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        r = page.rect

        # Résolution des zones à rendre.
        zones: list[tuple[str, "fitz.Rect | None"]]
        if custom_rect and all(k in custom_rect for k in ("x", "y", "w", "h")):
            # Rectangle custom en ratios 0..1 du magazine
            # (persisté sur Magazine.ai_crop_rect via l'UI). Clampe
            # les bounds pour éviter les Rect invalides.
            cx = max(0.0, min(1.0, float(custom_rect["x"])))
            cy = max(0.0, min(1.0, float(custom_rect["y"])))
            cw = max(0.01, min(1.0 - cx, float(custom_rect["w"])))
            ch = max(0.01, min(1.0 - cy, float(custom_rect["h"])))
            zones = [("custom", fitz.Rect(
                r.x0 + r.width * cx,
                r.y0 + r.height * cy,
                r.x0 + r.width * (cx + cw),
                r.y0 + r.height * (cy + ch),
            ))]
        elif crop_mode == "top":
            zones = [("top", fitz.Rect(
                r.x0, r.y0, r.x1, r.y0 + r.height * 0.45,
            ))]
        elif crop_mode == "bottom":
            zones = [("bottom", fitz.Rect(
                r.x0, r.y0 + r.height * 0.55, r.x1, r.y1,
            ))]
        elif crop_mode == "top_bottom":
            zones = [
                ("top", fitz.Rect(
                    r.x0, r.y0, r.x1, r.y0 + r.height * 0.45,
                )),
                ("bottom", fitz.Rect(
                    r.x0, r.y0 + r.height * 0.55, r.x1, r.y1,
                )),
            ]
        else:  # "full" or unknown
            zones = [("full", None)]

        out: list[tuple[str, bytes]] = []
        for label, clip in zones:
            pix = page.get_pixmap(matrix=matrix, alpha=False, clip=clip)
            out.append((label, pix.tobytes(output="png")))
        return out
    finally:
        doc.close()


# Legacy wrapper — kept to avoid breaking any external caller.
def _render_page_png(
    pdf_path: Path,
    page_index_1based: int,
    dpi: int = 200,
    crop_top_ratio: float | None = None,
) -> bytes:
    mode = "top" if crop_top_ratio else "full"
    return _render_page_pngs(pdf_path, page_index_1based, dpi, mode)[0][1]


class AIEnrichmentService:
    """Owns the enrichment pipeline. Stateless between calls.

    ``config`` : app Config (holds ai_* fields).
    ``session_factory`` : callable returning a fresh AsyncSession
    context manager (used for cache lookup + run persistence). The
    caller is expected to pass an ``async_sessionmaker`` reference
    so this service doesn't depend on the request-scoped DB.
    """

    def __init__(self, config, session_factory) -> None:
        self._config = config
        self._session_factory = session_factory
        self._ollama = OllamaAdapter(
            url=config.ai_ollama_url, timeout_s=config.ai_ollama_timeout_s
        )

    async def enrich(
        self,
        torrent_name: str,
        pdf_path: Path | None,
        magazine_id: int | None,
        issue_id: int | None,
        trigger: str,
        progress_cb: ProgressCb | None = None,
        force: bool = False,
    ) -> EnrichmentResult:
        """Run the full pipeline. Never raises — degrades to fallback.

        ``torrent_name`` : usually the source filename ; used verbatim
        by the text LLM prompt.
        ``pdf_path`` : local path to the imported PDF ; None → skip
        vision step entirely (text-only enrichment).
        ``trigger`` : "grab_auto" | "import_manual" | "reanalyze" —
        stored on the run for history filtering.
        ``progress_cb(stage, detail)`` : optional hook the caller
        wires to its queue progress step.
        """
        cfg = self._config
        cb = progress_cb or (lambda s, d: None)
        t0 = time.monotonic()

        pdfhash = pdf_hash(pdf_path)
        steps: list[dict[str, Any]] = []

        # --- 0. Cache check --------------------------------------
        # `force=True` bypasse le cache — utilisé quand l'user relance
        # explicitement (bouton « Refresh IA… »). Sinon on retourne
        # le dernier run success identique instantanément.
        if not force:
            cached = await self._lookup_cache(magazine_id, pdfhash)
            if cached is not None:
                cb("cache", "hit — utilisation du dernier résultat validé")
                return EnrichmentResult(
                    final=cached["final"],
                    applied_mode="cache_hit",
                    run_id=cached["id"],
                    steps=cached["steps"],
                    total_elapsed_ms=cached["total_elapsed_ms"],
                )

        # --- Create the run row up-front so the UI can poll ------
        run_id = await self._create_run_row(
            magazine_id=magazine_id,
            issue_id=issue_id,
            trigger=trigger,
            pdf_hash=pdfhash,
        )

        # --- Guard 1 : Ollama reachable + models present ---------
        available = await self._ollama.list_models()
        if not available:
            cb("skip", "Ollama injoignable — fallback parser natif")
            return await self._finalize_skip(run_id, steps, t0, "ollama_unreachable")
        if cfg.ai_text_model not in available:
            cb("skip", f"Modèle texte '{cfg.ai_text_model}' absent — fallback")
            return await self._finalize_skip(run_id, steps, t0, "text_model_missing")

        # --- 1. Text LLM ----------------------------------------
        cb("text", f"Analyse nom torrent avec {cfg.ai_text_model}")
        text_result, text_step = await self._call_json(
            model=cfg.ai_text_model,
            prompt=(
                f"{cfg.ai_text_prompt}\n\n---\nNom de fichier : "
                f"{torrent_name}"
            ),
            step_name="text",
        )
        steps.append(text_step)

        # --- Guard 2 : vision available? ------------------------
        vision_outputs: list[dict[str, Any]] = []
        has_vision = (
            pdf_path is not None
            and cfg.ai_vision_model in available
            and cfg.ai_enrichment_vision_pages
        )
        if pdf_path is None:
            cb("skip", "Pas de PDF fourni — enrichissement texte seul")
        elif cfg.ai_vision_model not in available:
            cb("skip", f"Modèle vision '{cfg.ai_vision_model}' absent — texte seul")
        elif not cfg.ai_enrichment_vision_pages:
            cb("skip", "Aucune page vision configurée — texte seul")

        if has_vision:
            # --- 2. Switch : unload text, load vision ---------
            cb("switch", f"Chargement modèle vision {cfg.ai_vision_model}…")
            await self._ollama.unload_model(cfg.ai_text_model)

            pages = cfg.ai_enrichment_vision_pages or [1]
            crop_mode = getattr(cfg, "ai_enrichment_vision_crop", "full")
            # Custom rect prioritaire : l'user l'a défini visuellement
            # dans le UI Refresh IA → persisté sur Magazine.ai_crop_rect.
            custom_rect = await self._lookup_magazine_crop(magazine_id)
            # Chaque page peut générer 1 ou 2 crops (top_bottom).
            # On les traite comme des appels vision distincts et on
            # laisse l'arbitre déterministe agréger.
            for idx, page_num in enumerate(pages, 1):
                try:
                    rendered = _render_page_pngs(
                        pdf_path,
                        page_num,
                        crop_mode=crop_mode,
                        custom_rect=custom_rect,
                    )
                except (IndexError, Exception) as exc:  # noqa: BLE001
                    logger.warning(
                        "Page %s render failed: %s", page_num, exc
                    )
                    steps.append({
                        "step": "vision",
                        "page": page_num,
                        "model": cfg.ai_vision_model,
                        "output": None,
                        "error": f"render_failed: {exc}",
                        "elapsed_ms": 0,
                    })
                    continue

                import base64
                for zone_label, png_bytes in rendered:
                    cb(
                        "vision",
                        f"OCR page {page_num} · zone {zone_label} "
                        f"({idx}/{len(pages)})",
                    )
                    img_b64 = base64.b64encode(png_bytes).decode("ascii")
                    v_output, v_step = await self._call_json(
                        model=cfg.ai_vision_model,
                        prompt=cfg.ai_vision_prompt,
                        step_name="vision",
                        images_b64=[img_b64],
                        extra_step_fields={
                            "page": page_num,
                            "zone": zone_label,
                        },
                    )
                    steps.append(v_step)
                    if v_output is not None:
                        vision_outputs.append({
                            "page": page_num,
                            "zone": zone_label,
                            "data": v_output,
                        })

            # --- 4. Switch back to text model for arbiter -----
            cb("switch", f"Rechargement modèle arbitre {cfg.ai_text_model}…")
            await self._ollama.unload_model(cfg.ai_vision_model)

        # --- 5. Arbitrage hybride : Python propose, LLM tranche ---
        # Architecture 3-couches :
        #   a) Python parse le raw_text vision avec regex → candidates
        #      (rapide, deterministic, mais peut manquer cas edge)
        #   b) LLM arbitre reçoit : torrent + vision_raw + python_candidates
        #      → choisit la valeur la plus réaliste par champ
        #   c) Post-validation Python : force torrent-primary sur les
        #      champs non-null torrent (l'IA ne peut PAS écraser)
        if vision_outputs:
            cb("arbiter", "Analyse Python + arbitrage IA")
            arb_start = time.monotonic()

            # a) Python propose ses candidats depuis le raw_text vision
            python_candidates = _arbitrate(text_result or {}, vision_outputs)

            # b) LLM arbitre — reçoit les 3 sources et tranche.
            llm_final = None
            llm_err = None
            if cfg.ai_text_model in available:
                arb_prompt = _build_arbiter_prompt(
                    torrent=text_result or {},
                    vision_outputs=vision_outputs,
                    python_candidates=python_candidates,
                    base_prompt=cfg.ai_arbiter_prompt,
                )
                llm_out, arb_step = await self._call_json(
                    model=cfg.ai_text_model,
                    prompt=arb_prompt,
                    step_name="arbiter",
                )
                steps.append(arb_step)
                if isinstance(llm_out, dict):
                    llm_final = llm_out
                else:
                    llm_err = arb_step.get("error") or "empty response"
            else:
                llm_err = f"arbiter model '{cfg.ai_text_model}' unavailable"

            # c) Post-validation : garantit torrent-primary.
            if llm_final is None:
                logger.info(
                    "Arbiter LLM unavailable (%s), using Python candidates",
                    llm_err,
                )
                final = python_candidates
            else:
                final = _postvalidate_arbiter(
                    llm_out=llm_final,
                    torrent=text_result or {},
                    python_candidates=python_candidates,
                )
                steps.append({
                    "step": "arbiter_postvalidate",
                    "model": "deterministic-python",
                    "output": final,
                    "error": None,
                    "elapsed_ms": int((time.monotonic() - arb_start) * 1000),
                })
        else:
            final = text_result or {}

        # --- 6. Persist ------------------------------------------
        cb("done", f"{sum(1 for k, v in final.items() if v is not None)} champs extraits")
        elapsed = int((time.monotonic() - t0) * 1000)
        applied = cfg.ai_enrichment_mode
        await self._finalize_run(
            run_id=run_id,
            steps=steps,
            final=final,
            applied_mode=applied,
            elapsed_ms=elapsed,
            status="success",
        )
        return EnrichmentResult(
            final=final,
            applied_mode=applied,
            run_id=run_id,
            steps=steps,
            total_elapsed_ms=elapsed,
        )

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------

    async def _call_json(
        self,
        *,
        model: str,
        prompt: str,
        step_name: str,
        images_b64: list[str] | None = None,
        extra_step_fields: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Wrap an Ollama call with timing + step recording.

        Returns ``(output, step_record)``. On failure, ``output`` is
        None and ``step_record["error"]`` holds the message. Never
        raises — the pipeline must be able to continue with partial
        data.
        """
        t0 = time.monotonic()
        step: dict[str, Any] = {
            "step": step_name,
            "model": model,
            "output": None,
            "error": None,
            "elapsed_ms": 0,
        }
        if extra_step_fields:
            step.update(extra_step_fields)
        # Vision calls (with images) : context ≥ 4096 sature vite car
        # une image PDF encodée base64 mange 2000-4000 tokens vision.
        # Compromis 8192 : assez pour une image 200 DPI + prompt + JSON
        # sortie, sans faire exploser le KV cache VRAM (qwen2.5vl:7b
        # + 16384 ctx demandait 18 Go, trop pour une 8 Go). Pour un
        # modèle plus léger ou une VRAM plus grosse, remonter à 16384.
        num_ctx = 8192 if images_b64 else None
        try:
            out = await self._ollama.generate_json(
                model=model,
                prompt=prompt,
                images_b64=images_b64,
                num_ctx=num_ctx,
            )
            step["output"] = out
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            return out, step
        except OllamaError as exc:
            step["error"] = str(exc)
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            logger.warning("AI step %s failed: %s", step_name, exc)
            return None, step

    async def _lookup_magazine_crop(
        self, magazine_id: int | None
    ) -> dict[str, float] | None:
        """Charge le rectangle custom sauvegardé sur le magazine.

        Renvoie ``None`` si magazine_id est None, aucun row trouvé, ou
        que le champ est vide/malformé — le rendu tombera alors sur
        le mode global (``full``/``top``/…).
        """
        if magazine_id is None:
            return None
        from sqlalchemy import select
        from app.models.magazine import Magazine
        try:
            async with self._session_factory() as session:
                row = (
                    await session.execute(
                        select(Magazine.ai_crop_rect).where(
                            Magazine.id == magazine_id
                        )
                    )
                ).first()
                raw = row[0] if row else None
                if not raw:
                    return None
                data = json.loads(raw)
                if all(k in data for k in ("x", "y", "w", "h")):
                    return {
                        "x": float(data["x"]),
                        "y": float(data["y"]),
                        "w": float(data["w"]),
                        "h": float(data["h"]),
                    }
        except Exception as exc:  # noqa: BLE001
            logger.warning("magazine crop lookup failed: %s", exc)
        return None

    async def _lookup_cache(
        self, magazine_id: int | None, pdfhash: str
    ) -> dict[str, Any] | None:
        """Return the newest successful run for this (magazine, pdf) or None.

        Cache is disabled when magazine_id is None (freshly parsed
        file, no magazine matched yet) — the run still writes to the
        journal for debug but subsequent identical runs won't skip.
        """
        if magazine_id is None:
            return None
        from sqlalchemy import select

        from app.models.ai_run import AIEnrichmentRun

        async with self._session_factory() as session:
            q = (
                select(AIEnrichmentRun)
                .where(
                    AIEnrichmentRun.magazine_id == magazine_id,
                    AIEnrichmentRun.pdf_hash == pdfhash,
                    AIEnrichmentRun.status == "success",
                )
                .order_by(AIEnrichmentRun.started_at.desc())
                .limit(1)
            )
            row = (await session.execute(q)).scalars().first()
            if not row:
                return None
            return {
                "id": row.id,
                "final": json.loads(row.final_json or "{}"),
                "applied_mode": row.applied_mode,
                "steps": json.loads(row.steps_json or "[]"),
                "total_elapsed_ms": row.total_elapsed_ms,
            }

    async def _create_run_row(
        self,
        *,
        magazine_id: int | None,
        issue_id: int | None,
        trigger: str,
        pdf_hash: str,
    ) -> int:
        from app.models.ai_run import AIEnrichmentRun

        async with self._session_factory() as session:
            run = AIEnrichmentRun(
                magazine_id=magazine_id,
                issue_id=issue_id,
                trigger=trigger,
                pdf_hash=pdf_hash,
                status="running",
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run.id

    async def _finalize_run(
        self,
        *,
        run_id: int,
        steps: list[dict[str, Any]],
        final: dict[str, Any],
        applied_mode: str,
        elapsed_ms: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        from datetime import datetime

        from sqlalchemy import select

        from app.models.ai_run import AIEnrichmentRun

        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(AIEnrichmentRun).where(AIEnrichmentRun.id == run_id)
                )
            ).scalars().first()
            if row is None:
                return
            row.steps_json = json.dumps(steps, ensure_ascii=False)
            row.final_json = json.dumps(final, ensure_ascii=False)
            row.applied_mode = applied_mode
            row.total_elapsed_ms = elapsed_ms
            row.status = status
            row.error_message = error_message
            row.completed_at = datetime.utcnow()

            # History event so the run is visible in the timeline. Best-
            # effort — a FK violation on magazine_id/issue_id must not
            # break the run save.
            try:
                from app.services.history_service import create_event
                # Summarise the run for the history UI : keep only the
                # non-null fields from `final` + per-step statuses.
                summary_fields = {
                    k: v for k, v in (final or {}).items()
                    if v is not None and v != "" and v != []
                }
                step_summary = [
                    {
                        "step": s.get("step"),
                        "model": s.get("model"),
                        "page": s.get("page"),
                        "error": s.get("error"),
                        "output": s.get("output"),
                        "elapsed_ms": s.get("elapsed_ms"),
                    }
                    for s in (steps or [])
                ]
                await create_event(
                    session,
                    event_type="ai_enrichment",
                    magazine_id=row.magazine_id,
                    issue_id=row.issue_id,
                    details=(
                        f"IA enrichissement · {status} · "
                        f"{len(step_summary)} étape(s) · {elapsed_ms}ms"
                    ),
                    data={
                        "run_id": run_id,
                        "trigger": row.trigger,
                        "status": status,
                        "applied_mode": applied_mode,
                        "final": summary_fields,
                        "steps": step_summary,
                        "error_message": error_message,
                        "total_elapsed_ms": elapsed_ms,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "History event for AI run %s failed: %s", run_id, exc
                )
                try:
                    await session.rollback()
                    # Retry the AI run save without the history event.
                    row = (
                        await session.execute(
                            select(AIEnrichmentRun).where(AIEnrichmentRun.id == run_id)
                        )
                    ).scalars().first()
                    if row:
                        row.steps_json = json.dumps(steps, ensure_ascii=False)
                        row.final_json = json.dumps(final, ensure_ascii=False)
                        row.applied_mode = applied_mode
                        row.total_elapsed_ms = elapsed_ms
                        row.status = status
                        row.error_message = error_message
                        row.completed_at = datetime.utcnow()
                except Exception:  # noqa: BLE001
                    pass
            await session.commit()

    async def _finalize_skip(
        self,
        run_id: int,
        steps: list[dict[str, Any]],
        started_monotonic: float,
        reason: str,
    ) -> EnrichmentResult:
        elapsed = int((time.monotonic() - started_monotonic) * 1000)
        await self._finalize_run(
            run_id=run_id,
            steps=steps,
            final={},
            applied_mode="skipped_fallback",
            elapsed_ms=elapsed,
            status="skipped",
            error_message=reason,
        )
        return EnrichmentResult(
            final={},
            applied_mode="skipped_fallback",
            run_id=run_id,
            steps=steps,
            total_elapsed_ms=elapsed,
        )


def merge_ai_into_parsed(parsed, ai_final: dict[str, Any], mode: str) -> Any:
    """Apply AI extraction to a Parsed dataclass per autorité mode.

    ``parsed`` : the object returned by ``parse_magazine_filename``.
    Fields we override : title, number, year, month, day, is_hs
    (mapped to `is_special` on Issue downstream), series_number.

    ``mode`` :
      - ``remplace``  : any AI non-null value wins over parsed
      - ``complete``  : AI fills in only when parsed field is null
      - ``propose``   : parsed untouched (proposals table handles it)
      - anything else : no-op (defensive)
    """
    if mode in ("propose", "skipped_fallback") or not ai_final:
        return parsed

    field_map = {
        "title": "title",
        "issue_number": "number",
        "year": "year",
        "month": "month",
        "day": "day",
    }
    for ai_key, parsed_key in field_map.items():
        ai_val = ai_final.get(ai_key)
        if ai_val is None:
            continue
        current = getattr(parsed, parsed_key, None)
        if mode == "remplace":
            setattr(parsed, parsed_key, ai_val)
        elif mode == "complete" and current is None:
            setattr(parsed, parsed_key, ai_val)
    return parsed
