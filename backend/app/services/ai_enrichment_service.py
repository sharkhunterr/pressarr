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
import re
import time
import unicodedata as _unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.services.ai_ollama_adapter import (
    OllamaAdapter,
    OllamaError,
    encode_image_file,
)

logger = logging.getLogger(__name__)


def _scrub_surrogates(v: Any) -> Any:
    """Nettoie récursivement les surrogates non-pairés (\\ud800-\\udfff).

    Le vision LLM renvoie parfois des emojis coupés ou des chars
    Windows-1252 orphelins → SQLite refuse le write avec
    ``UnicodeEncodeError: surrogates not allowed``. Cette fonction
    passe une string dans encode-replace-decode pour remplacer tout
    orphelin par '\\ufffd'.
    """
    if isinstance(v, str):
        return v.encode("utf-8", errors="replace").decode("utf-8")
    if isinstance(v, dict):
        return {k: _scrub_surrogates(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_scrub_surrogates(x) for x in v]
    return v


def _safe_json_dumps(obj: Any) -> str:
    """json.dumps avec scrub des surrogates + ensure_ascii=False."""
    return json.dumps(_scrub_surrogates(obj), ensure_ascii=False, default=str)


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


# ─── ZONE TAG → ISSUE FIELD MAPPING ───────────────────────────────────
#
# Chaque tag de zone (défini dans le sélecteur visuel côté frontend)
# est routé vers un champ Issue précis. Le vision LLM extrait le
# raw_text de la zone → routé directement vers le field sans regex
# heuristique (promesse UI : ce que tu tagges, ça remplit CE champ).
#
# Pour ajouter un nouveau field extractible via zone :
#   1. Ajoute la column dans app.models.issue.Issue + migration main.py
#   2. Ajoute le tag ici dans TAG_TO_FIELD
#   3. Ajoute le prompt vision dans _ZONE_TAG_FOCUS ci-dessous
#   4. Ajoute le champ dans le JSON output de _build_arbiter_prompt
#   5. Ajoute le mapping dans merge_ai_into_parsed
#   6. Ajoute l'option dans le frontend ZONE_TAGS
#
TAG_TO_FIELD: dict[str, str | None] = {
    "number":    "number",
    "date":      "publication_date",  # split en year/month/day à l'ingestion
    "title":     "title",
    "subtitle":  "subtitle",
    "price":     "price",
    "issn":      "issn",
    "publisher": None,  # remplit magazine.publisher, PAS l'issue
    "all":       None,  # tag "tout" — le pipeline extrait tout ce qu'il peut
    "custom":    None,  # consigne libre, pas de field cible
}


_ZONE_TAG_FOCUS: dict[str, str] = {
    # Le suffixe est concaténé au prompt vision de base pour orienter
    # le modèle sans réécrire tout le contrat JSON.
    "number": (
        "\n\n---\n### FOCUS ZONE\nCette zone contient UNIQUEMENT le "
        "numéro d'édition du magazine (ex. « N° 4033 », « No 26 290 »). "
        "Ignore tout le reste. Renvoie ce numéro dans raw_text — "
        "un seul entier suffit si tu ne vois que ça."
    ),
    "date": (
        "\n\n---\n### FOCUS ZONE\nCette zone contient UNIQUEMENT la "
        "date de publication (ex. « lundi 10 août 2026 », « Mars 2024 », "
        "« DU 13 AU 19 AOÛT 2026 »). Ignore tout le reste. Renvoie la "
        "date lisiblement dans raw_text."
    ),
    "title": (
        "\n\n---\n### FOCUS ZONE\nCette zone contient UNIQUEMENT le "
        "titre principal du magazine (le logo/nom du journal). Ignore "
        "les titres d'articles/accroches. Renvoie le titre dans raw_text "
        "ET dans title."
    ),
    "subtitle": (
        "\n\n---\n### FOCUS ZONE\nCette zone contient un sous-titre ou "
        "une accroche éditoriale. Renvoie le texte tel quel dans raw_text."
    ),
    "price": (
        "\n\n---\n### FOCUS ZONE\nCette zone contient le prix + éventuelles "
        "mentions tarifaires étrangères (« 4,00 € », « BEL: 4,40 € »). "
        "Renvoie tout ça dans raw_text."
    ),
    "publisher": (
        "\n\n---\n### FOCUS ZONE\nCette zone contient l'éditeur / les "
        "mentions légales / le domaine (« www.lefigaro.fr », « Editions "
        "Prisma »). Renvoie tout ça dans raw_text."
    ),
    "issn": (
        "\n\n---\n### FOCUS ZONE\nCette zone contient UNIQUEMENT le "
        "numéro ISSN du magazine (format « ISSN 1234-5678 » ou juste "
        "« 1234-5678 » — 8 chiffres/lettres séparés par un tiret). "
        "Ignore le reste. Renvoie l'ISSN dans raw_text."
    ),
    "all": "",  # comportement historique (prompt entier tel quel)
}


def _build_zone_vision_prompt(
    *,
    base_prompt: str,
    tag: str,
    custom_tag: str | None = None,
) -> str:
    """Concat un focus ciblé au prompt vision selon le tag de zone.

    Le focus est ajouté APRÈS le prompt de base pour ne pas casser
    l'anti-triche déjà en place ; il ne remplace jamais les règles
    d'anti-hallucination. Pour ``tag == "custom"``, ``custom_tag``
    devient une consigne libre injectée directement.
    """
    if tag == "custom" and custom_tag:
        focus = (
            "\n\n---\n### FOCUS ZONE\nConsigne opérateur : "
            f"{custom_tag.strip()}"
        )
        return base_prompt + focus
    suffix = _ZONE_TAG_FOCUS.get(tag, "")
    return base_prompt + suffix


# ─── AI RUN CROP CACHE ────────────────────────────────────────────────
#
# Chaque zone envoyée aux OCR est sauvée en PNG dans
# `<config_dir>/ai_run_crops/<run_id>/`. L'endpoint
# `/api/v1/ai/runs/{run_id}/crop/{page}_{label}.png` la sert au front
# pour que l'User voie EXACTEMENT ce qui a été envoyé (résolution,
# recadrage, rotation appliquée).

_RUN_CROPS_KEEP = 30  # nb de runs récents à garder sur disque


def _run_crops_root(config: Any) -> Path:
    """Racine du cache disque des crops par run.
    Créée à la demande (idempotent)."""
    root = Path(config.config_path).parent / "ai_run_crops"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_slug(s: str) -> str:
    """Filesystem-safe slug — garde alphanum, tiret, underscore, dot."""
    out = []
    for ch in s or "":
        if ch.isalnum() or ch in "-_.":
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)[:80] or "zone"


def _save_run_crop(
    config: Any, run_id: int, page: int, zone_label: str, png_bytes: bytes,
) -> str | None:
    """Sauve le crop pour un run donné, renvoie le nom de fichier
    (relatif à `run_id/`). Best-effort — un fail disque ne casse
    jamais le pipeline (juste pas d'image dans l'History)."""
    try:
        run_dir = _run_crops_root(config) / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{page}_{_safe_slug(zone_label)}.png"
        (run_dir / fname).write_bytes(png_bytes)
        return fname
    except Exception as exc:  # noqa: BLE001
        logger.warning("Save run crop %s/%s failed: %s", run_id, zone_label, exc)
        return None


def _cleanup_old_run_crops(config: Any) -> None:
    """Garde les `_RUN_CROPS_KEEP` runs les plus récents sur disque.
    Best-effort, jamais fatal."""
    try:
        root = _run_crops_root(config)
        dirs = [
            d for d in root.iterdir()
            if d.is_dir() and d.name.isdigit()
        ]
        if len(dirs) <= _RUN_CROPS_KEEP:
            return
        # sort by run_id desc (int-cast), drop oldest
        dirs.sort(key=lambda d: int(d.name), reverse=True)
        for d in dirs[_RUN_CROPS_KEEP:]:
            import shutil
            shutil.rmtree(d, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Cleanup ai_run_crops failed: %s", exc)


# Placeholders que minicpm-v recopie parfois depuis un ancien prompt
# example (même si le prompt actuel n'en contient plus). Signature nette.
_VISION_PLACEHOLDER_TOKENS = (
    "<TITRE>", "<MAGAZINE>", "<SOUS-TITRE>", "<SOUSTITRE>",
    "<NOUVELLE-EDITION>", "<NUMÉRO>", "<NUMERO>", "<JOUR>",
    "<DATE>", "<DATE-EN-TOUTES-LETTRES>", "<ANNÉE>", "<ANNEE>",
    "<affichage publicitaire>",
)

# HTML/XML tags jamais légitimes dans un OCR — minicpm-v en produit
# quand il « imagine » être en mode structured output.
_HTML_TAG_RE = re.compile(r"<\s*/?\s*(table|tr|td|tbody|thead|div|span|p|img|image|line|logo|strong|em|sub|sup|small|br|hr|ul|ol|li|a|body|html)\b[^>]*>", re.IGNORECASE)


def _scrub_vision_text(text: str) -> str:
    """Nettoie un raw_text vision de tout ce qu'un OCR ne devrait pas
    produire mais que minicpm-v injecte parfois :
      - Private Use Area (-)
      - HTML/XML tags
      - Caractères de contrôle (hors \n \t)
      - Placeholders littéraux (< TITRE >…)
    Ne touche PAS aux vrais accents FR ni au symbole €.
    Idempotent."""
    if not isinstance(text, str) or not text:
        return text
    for ph in _VISION_PLACEHOLDER_TOKENS:
        text = text.replace(ph, "")
    text = _HTML_TAG_RE.sub("", text)
    cleaned: list[str] = []
    for ch in text:
        cp = ord(ch)
        if 0xE000 <= cp <= 0xF8FF:
            continue  # PUA — jamais légitime
        if 0xF0000 <= cp <= 0x10FFFF:
            continue  # Supplementary PUA
        cat_first = _unicodedata.category(ch)[0]
        if cat_first == "C" and ch not in ("\n", "\t"):
            continue
        cleaned.append(ch)
    return "".join(cleaned)


def scrub_vision_output(vision_out: dict[str, Any]) -> dict[str, Any]:
    """Applique `_scrub_vision_text` à tous les champs textuels de la
    sortie vision. Retourne un nouveau dict (n'altère pas l'entrée)."""
    if not isinstance(vision_out, dict):
        return vision_out
    return {
        k: _scrub_vision_text(v) if isinstance(v, str) else v
        for k, v in vision_out.items()
    }


def _is_vision_garbage(vision_out: dict[str, Any]) -> tuple[bool, str]:
    """Détecte les sorties vision « poubelle » — mojibake, CJK massif,
    caractères de contrôle, symboles bizarres, HTML tags, placeholders.

    Cible principale : minicpm-v qui sort parfois des blocs de kanji /
    caractères Zalgo / répétitions de glyphes non-ASCII quand l'image
    l'a désorienté (bandeau trop étroit, zone quasi-vide, texte pivoté),
    ou qui recopie un placeholder ( <TITRE>, <MAGAZINE> ) au lieu de
    lire l'image.

    Cette fonction est appliquée SUR LA SORTIE BRUTE, avant scrub.
    Renvoie (True, raison) si la sortie doit être ignorée.
    """
    if not isinstance(vision_out, dict):
        return False, ""
    parts: list[str] = []
    for k in ("title", "raw_text", "publisher", "date", "issue_number"):
        v = vision_out.get(k)
        if isinstance(v, str):
            parts.append(v)
    blob = " ".join(parts).strip()
    if len(blob) < 2:
        return False, ""

    # 1. Placeholders : signature nette d'une hallucination de prompt.
    blob_upper = blob.upper()
    for ph in _VISION_PLACEHOLDER_TOKENS:
        if ph.upper() in blob_upper:
            return True, f"placeholder recopié ({ph})"

    # 2. HTML/XML tags : jamais légitime en OCR.
    if _HTML_TAG_RE.search(blob):
        return True, "balise HTML/XML dans le texte OCR"

    ctrl = 0
    weird_sym = 0
    pua = 0
    non_latin = 0
    foreign_script = 0
    foreign_sample = ""
    total = 0
    for ch in blob:
        if ch.isspace():
            continue
        total += 1
        cat = _unicodedata.category(ch)
        if cat in ("Cc", "Cf", "Cs"):
            ctrl += 1
            continue
        cp = ord(ch)
        # Private Use Area — TOUJOURS garbage (glyphes propriétaires).
        if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0x10FFFF:
            pua += 1
            weird_sym += 1
            non_latin += 1
            continue
        # Latin étendu OK
        if cp < 0x0250 or 0x1E00 <= cp <= 0x1EFF:
            continue
        # Scripts jamais légitimes dans un OCR de magazine FR :
        # présence d'UN SEUL caractère de ces scripts = garbage
        # (contrairement aux Latin étendus rares qui peuvent apparaître
        # dans un nom propre). Un magazine étranger vrai passerait par
        # le seuil ratio non_latin.
        is_foreign = (
            0x0370 <= cp <= 0x03FF   # Greek
            or 0x0400 <= cp <= 0x052F  # Cyrillic (+ supplement)
            or 0x0590 <= cp <= 0x077F  # Hebrew + Arabic + Syriac
            or 0x0900 <= cp <= 0x097F  # Devanagari
            or 0x2E80 <= cp <= 0x2EFF  # CJK radicals
            or 0x3000 <= cp <= 0x9FFF  # CJK
        )
        if is_foreign:
            foreign_script += 1
            if len(foreign_sample) < 8:
                foreign_sample += ch
            non_latin += 1
            continue
        # Symboles techniques / formes numériques / dingbats
        if (
            0x2150 <= cp <= 0x218F  # Number forms (½, ↉, ↋…)
            or 0x2190 <= cp <= 0x21FF  # arrows
            or 0x2200 <= cp <= 0x22FF  # mathematical
            or 0x2300 <= cp <= 0x23FF  # misc technical
            or 0x2500 <= cp <= 0x257F  # box drawing
            or 0x2580 <= cp <= 0x259F  # block elements
            or 0x25A0 <= cp <= 0x25FF  # geometric
            or 0x2700 <= cp <= 0x27BF  # dingbats
            or 0xA700 <= cp <= 0xA7FF  # Modifier tone / Latin ext-D
        ):
            weird_sym += 1
        non_latin += 1
    if total == 0:
        return False, ""
    if pua > 0:
        return True, f"{pua} caractère(s) Private Use Area"
    if ctrl > 3:
        return True, f"{ctrl} caractères de contrôle"
    if foreign_script > 0:
        return True, f"caractère(s) script étranger ({foreign_sample!r})"
    if weird_sym > 0:
        return True, f"{weird_sym} symbole(s) technique(s)/dingbat"
    ratio = non_latin / total
    if ratio > 0.15 and non_latin > 3:
        return True, f"{non_latin}/{total} chars hors latin ({ratio:.0%})"
    return False, ""


def _is_vision_leak(
    vision_out: dict[str, Any],
    expected_title_lower: str,
) -> bool:
    """Heuristique anti-hallucination : la sortie vision recopie-t-elle
    un titre de magazine différent de celui attendu ?

    Cible principale : minicpm-v qui régurgite parfois un exemple de
    magazine « célèbre » du prompt (L'ÉQUIPE, Le Monde, Paris Match…)
    quand on lui envoie une image qu'il ne sait pas lire (bandeau
    trop étroit, texte pivoté, photo sans texte).

    Renvoie True si la vision remonte un titre qui n'a AUCUN mot
    commun avec le titre torrent (ex. torrent=« Paris Match » et
    vision=« L'Équipe » → 0 mot commun → leak).
    Si ``expected_title_lower`` est vide → False (impossible de juger).
    """
    if not expected_title_lower or not isinstance(vision_out, dict):
        return False
    # On extrait UN candidat de titre : soit vision.title, soit la
    # première ligne du raw_text (souvent le titre du masthead).
    candidate = vision_out.get("title")
    if not (isinstance(candidate, str) and candidate.strip()):
        rt = vision_out.get("raw_text") or ""
        if isinstance(rt, str) and rt.strip():
            candidate = rt.strip().splitlines()[0]
    if not (isinstance(candidate, str) and candidate.strip()):
        return False
    cand_lower = candidate.lower()
    # Tokens simples : mots ≥ 3 lettres après retrait apostrophes/accents
    import re as _re
    def _toks(s: str) -> set[str]:
        s = s.lower().replace("'", "'").replace("l'", "").replace("le ", " ").replace("la ", " ")
        return {t for t in _re.split(r"[^a-zàâäéèêëïîôöùûüç0-9]+", s) if len(t) >= 3}
    expected = _toks(expected_title_lower)
    got = _toks(cand_lower)
    # Si on n'a même pas 1 token attendu à comparer, on ne peut pas juger
    if not expected:
        return False
    return expected.isdisjoint(got)


def _arbitrate(
    torrent: dict[str, Any],
    vision_outputs: list[dict[str, Any]],
    pyocr_outputs: list[dict[str, Any]] | None = None,
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
        "subtitle": torrent.get("subtitle"),
        "price": torrent.get("price"),
        "issue_number": torrent.get("issue_number"),
        "year": torrent.get("year"),
        "month": torrent.get("month"),
        "day": torrent.get("day"),
        "is_hs": bool(torrent.get("is_hs")),
        "series_number": torrent.get("series_number"),
        "issn": torrent.get("issn"),
    }

    for entry in vision_outputs:
        vd = entry.get("data") if isinstance(entry, dict) else {}
        if not isinstance(vd, dict):
            continue

        # Route DIRECT tag→field : si l'utilisateur a défini une zone
        # avec tag "subtitle" ou "price", son raw_text remplit
        # directement le champ correspondant sans regex heuristique.
        # C'est la promesse de l'UI zone tags : ce que tu tagges,
        # ça remplit exactement CE champ, rien d'autre.
        zone_tag = entry.get("tag") if isinstance(entry, dict) else None
        raw_text = vd.get("raw_text") if isinstance(vd.get("raw_text"), str) else ""
        raw_stripped = (raw_text or "").strip()
        if zone_tag == "subtitle" and out["subtitle"] is None and raw_stripped:
            out["subtitle"] = raw_stripped[:500]
        elif zone_tag == "price" and out["price"] is None and raw_stripped:
            out["price"] = raw_stripped[:32]

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

        if out.get("issn") is None:
            v = _extract_issn(text_pool)
            if v:
                out["issn"] = v

    # Source 3 déterministe : Python OCR (Tesseract/RapidOCR/EasyOCR)
    # sur le MÊME crop. Verse son raw_text dans le pool regex —
    # complémentaire du vision LLM (l'un rate ce que l'autre voit).
    for entry in pyocr_outputs or []:
        rt = entry.get("raw_text") if isinstance(entry, dict) else None
        if not (isinstance(rt, str) and rt.strip()):
            continue
        # Route direct tag→field pour python OCR aussi
        zone_tag = entry.get("tag") if isinstance(entry, dict) else None
        if zone_tag == "subtitle" and out["subtitle"] is None:
            out["subtitle"] = rt.strip()[:500]
        elif zone_tag == "price" and out["price"] is None:
            out["price"] = rt.strip()[:32]
        text_pool = rt
        if out["issue_number"] is None:
            parsed_num = _extract_issue_number(text_pool)
            if parsed_num is not None:
                out["issue_number"] = parsed_num
        if not all(out.get(k) is not None for k in ("year", "month", "day")):
            y, m, d = _parse_french_date(text_pool)
            if y and out.get("year") is None:
                out["year"] = y
            if m and out.get("month") is None:
                out["month"] = m
            if d and out.get("day") is None:
                out["day"] = d
        if out.get("issn") is None:
            v = _extract_issn(text_pool)
            if v:
                out["issn"] = v

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
    pyocr_outputs: list[dict[str, Any]] | None = None,
) -> str:
    """Construit le prompt de l'arbitre IA final.

    Le prompt liste jusqu'à 4 sources et demande à l'IA de choisir la
    valeur la plus RÉALISTE par champ :
      - Source 1 : torrent (fiabilité haute, primaire)
      - Source 2 : IA vision — OCR LLM (raw_text à trier, peut halluciner)
      - Source 3 : OCR algorithmique Python (Tesseract/EasyOCR/RapidOCR
                   — deterministic, jamais d'hallucination mais moins
                   robuste sur textes stylisés)
      - Source 4 : candidats regex Python (déjà filtrés)

    Les 2 OCR (IA + algo) tournent sur la MÊME image : leur
    corroboration renforce la confiance ; leur divergence signale
    un texte ambigu où l'arbiter doit trancher.
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

    # Concat des raw_text python OCR — même clef (page/zone) pour
    # que le LLM puisse cross-checker avec la source vision.
    pyocr_dump = []
    for entry in pyocr_outputs or []:
        rt = entry.get("raw_text") if isinstance(entry, dict) else None
        if not (isinstance(rt, str) and rt.strip()):
            continue
        page = entry.get("page", "?")
        zone = entry.get("zone", "?")
        engine = entry.get("engine", "?")
        pyocr_dump.append(
            f"[page {page} · zone {zone} · engine {engine}] {rt!r}"
        )
    pyocr_str = "\n".join(pyocr_dump) if pyocr_dump else "(aucune sortie python OCR)"

    return (
        f"{base_prompt}\n\n---\n"
        "Quatre sources sont disponibles pour extraire les métadonnées "
        "de ce magazine. Choisis la valeur la plus RÉALISTE par champ.\n\n"
        f"### Source 1 — Analyse du nom torrent (fiable, source primaire)\n"
        f"{json.dumps(torrent, ensure_ascii=False, indent=2)}\n\n"
        f"### Source 2 — OCR IA vision de la couverture (à trier)\n"
        f"{vision_str}\n\n"
        f"### Source 3 — OCR algorithmique (Tesseract/EasyOCR/RapidOCR) sur la MÊME image\n"
        f"{pyocr_str}\n\n"
        f"### Source 4 — Candidats extraits par regex (rapide mais imparfait)\n"
        f"{json.dumps(python_candidates, ensure_ascii=False, indent=2)}\n\n"
        "### Règles de décision\n"
        "1. Si la source 1 (torrent) a une valeur NON-NULL, garde-la — "
        "elle est toujours prioritaire.\n"
        "2. Sinon, préfère la source 4 (regex) car elle a déjà filtré "
        "les faux positifs comme « 2,70 € » (prix), « 81ᵉ année » "
        "(année d'existence du magazine), « 80 ans ».\n"
        "3. **Corroboration OCR IA + OCR algo** : si sources 2 et 3 "
        "s'accordent sur un chiffre (« N° 26 290 » dans les 2), la "
        "confiance est très élevée. Si elles divergent, préfère "
        "celle qui a le format le plus plausible (5 chiffres pour un "
        "quotidien, 4 pour un hebdo). L'OCR algo n'hallucine JAMAIS ; "
        "l'IA vision peut inventer sous pression — méfie-toi si "
        "seul le vision voit un mot que le python OCR n'a pas.\n"
        "4. Utilise les raw_text pour repérer les indices type "
        "« N° 26 290 », « lundi 10 août 2026 ». Si les 2 OCR ont "
        "raté un N° et que la source 4 ne l'a pas non plus, laisse-le "
        "null (pas d'invention).\n"
        "5. **Nombre avec espace = UN SEUL nombre.** « 26 290 » est le "
        "nombre 26290 (espace = séparateur milliers français), pas deux "
        "nombres 26 et 290. Écris-le concaténé SANS espace. Autres "
        "exemples : « 3 720 » → 3720, « 12 025 » → 12025. La règle "
        "s'applique DÈS QU'IL Y A un espace entre 2-3 chiffres puis "
        "exactement 3 chiffres. NE JAMAIS confondre les premiers 2 "
        "chiffres seuls avec un jour du mois — vérifie le contexte : "
        "un « N° » ou « No » devant, ou l'absence de nom de mois "
        "immédiatement après, prouve que c'est un numéro d'édition.\n"
        "6. Contre-exemple : « 12 août 2026 » = date (jour 12, mois août, "
        "année 2026). Ici l'espace sépare le jour et le mot « août », "
        "donc les 2 chiffres 12 sont bien un jour, pas un préfixe de "
        "numéro d'édition.\n"
        "7. N'invente PAS un N° si tu n'en vois pas dans les 4 sources.\n"
        "8. La date doit être cohérente : year + month + day quand possible. "
        "Ignore les années < 1900 ou > 2100.\n\n"
        "Réponds avec un objet JSON strict :\n"
        "{\"title\": str|null, \"subtitle\": str|null, "
        "\"issue_number\": int|null, "
        "\"year\": int|null, \"month\": int|null, \"day\": int|null, "
        "\"is_hs\": bool, \"series_number\": int|null, "
        "\"issn\": str|null, \"price\": str|null, "
        "\"confidence\": float}\n\n"
        "`title` : le NOM du magazine (ex. « Le Figaro », « Paris Match »).\n"
        "`subtitle` : sous-titre / accroche éditoriale visible sous le "
        "titre (ex. « L'affaire Epstein — nos révélations »). null si "
        "aucune zone tagged \"subtitle\" et aucun texte évident.\n"
        "`price` : prix affiché tel quel avec devise (ex. « 3,50 € », "
        "« US $ 5.99 », « CHF 4.50 »). GARDE le formatage original — "
        "on n'essaie pas de parser en float. null si absent.\n"
        "`issn` : format canonique ``NNNN-NNNC`` (ex. « 0242-6056 »). "
        "Extrais-le d'un « ISSN 1234-5678 » ou d'un pattern brut "
        "4-3+1 chiffres. Sinon null.\n"
        "`confidence` entre 0 et 1 = estimation globale de fiabilité.\n"
        "**IMPORTANT TYPES** : issue_number/year/month/day sont des "
        "INT (ex. `8` pas `\"Août\"` pas `\"08\"`). Convertis les noms "
        "de mois en numéros (Janvier=1..Décembre=12) avant de renvoyer."
    )


def _postvalidate_arbiter(
    *,
    llm_out: dict[str, Any],
    torrent: dict[str, Any],
    python_candidates: dict[str, Any],
) -> dict[str, Any]:
    """Contrainte post-LLM en 3 étages :

    1. **Torrent primaire absolu** : si le torrent a une valeur non-null
       pour un champ, l'arbitre IA ne peut PAS l'écraser (fix bug
       historique year=2016 vision qui écrasait year=2026 torrent).

    2. **Restauration Python** : si le LLM a mis un champ à null MAIS que
       Python (regex sur raw_text vision) avait trouvé une valeur, on
       restaure la valeur Python. Le LLM peut « oublier » de recopier
       ce que Python a déjà bien extrait — on ne veut pas perdre l'info.

    3. **Anti-hallucination** : si le LLM propose une valeur (typique
       issue_number) qui n'est PAS dans torrent NI python_candidates,
       on la refuse sauf si confidence >= 0.9 (le LLM a « vu » un truc
       explicit dans le raw_text que la regex a raté).
    """
    out = dict(llm_out)  # copy

    # Étage 1 : torrent primaire absolu.
    for field in ("title", "issue_number", "year", "month", "day"):
        torrent_val = torrent.get(field)
        if torrent_val is not None and torrent_val != "":
            out[field] = torrent_val

    # is_hs / series_number : garde torrent si dispo.
    if torrent.get("is_hs") is not None:
        out["is_hs"] = bool(torrent["is_hs"])
    else:
        out["is_hs"] = bool(out.get("is_hs"))
    if torrent.get("series_number") is not None:
        out["series_number"] = torrent["series_number"]

    # Étage 2 : restauration Python quand le LLM a « oublié ».
    # Bug user constaté : Python trouvait issue_number=26290 dans
    # « N° 26 290 » mais l'arbitre LLM le mettait à null → sortie null.
    # Le LLM n'a pas le droit de SUPPRIMER une info que Python a
    # extraite avec succès du raw_text vision.
    for field in ("issue_number", "title", "year", "month", "day", "series_number"):
        if out.get(field) is None and python_candidates.get(field) is not None:
            # Ne restaure que si le torrent est aussi null (l'étage 1
            # a déjà tranché sinon).
            if torrent.get(field) is None:
                out[field] = python_candidates[field]

    # Étage 3 : anti-hallucination pour issue_number.
    # Si LLM propose un N° qui n'est ni dans torrent ni dans python
    # → probablement inventé. On refuse sauf confidence >= 0.9.
    if (
        out.get("issue_number") is not None
        and torrent.get("issue_number") is None
        and python_candidates.get("issue_number") is None
        # ET aussi le LLM lui-même l'a proposé (pas restauré Python)
        and llm_out.get("issue_number") is not None
    ):
        conf = float(out.get("confidence") or 0.0)
        if conf < 0.9:
            out["issue_number"] = None

    return out


def _extract_issn(text: str) -> str | None:
    """Extrait un ISSN d'un blob texte.

    Format ISSN standard : 4 chiffres + tiret + 3 chiffres + 1 chiffre/X.
    Ex. « 0242-6056 », « ISSN 1234-567X ». Le préfixe « ISSN » est
    optionnel. On renvoie la forme canonique ``NNNN-NNNC``.
    """
    import re
    if not text:
        return None
    m = re.search(r"\b(\d{4})[-\s]?(\d{3}[\dXx])\b", text)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2).upper()}"


def _extract_issue_number(text: str) -> int | None:
    """Extrait le numéro d'édition d'un blob texte.

    Cherche des patterns « N°/No/# XXXXX » (avec espace optionnel au
    milieu du nombre) puis fallback sur un nombre à séparateur milliers
    (« 26 290 » = L'Équipe daily). Distingue des faux positifs :
      - « 81ᵉ année », « 80 ans » (année d'existence du magazine)
      - « 2,70 € », « 100 pages », « Rue de X 75001 »
      - dates ISO (« 2026-08-10 »), « 12 août 2026 »

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

    # Priorité 1bis : nombre 2-3 chiffres + espace + 3 chiffres sans
    # préfixe (« 26 290 » sur la Une quand l'OCR a raté le « N° »).
    # Contrainte : le PREMIER mot juste après NE doit PAS être un nom
    # de mois (sinon c'est jour+mois séparés par erreur d'OCR : « 12 août »).
    _MONTH_RE = re.compile(
        r"^\s*(janv|févr|fevr|mars|avril|mai|juin|juill|"
        r"août|aout|sept|oct|nov|déc|dec)\b",
        re.IGNORECASE,
    )
    for cand in re.finditer(r"\b(\d{2,3})\s(\d{3})\b", text):
        d1, d2 = cand.group(1), cand.group(2)
        # Guard : d2 est un préfixe année tronquée (« 12 025 » = 2025)
        if len(d2) == 3 and d2.startswith("0"):
            continue
        after = text[cand.end():cand.end() + 20]
        # Guard : mot juste après = mois → c'est une date jour+mois
        if _MONTH_RE.match(after):
            continue
        # Guard : contexte prix immédiat
        before = text[max(0, cand.start() - 4):cand.start()]
        if "€" in text[cand.end():cand.end() + 4]:
            continue
        if "€" in before:
            continue
        try:
            n = int(d1 + d2)
            if not (1900 <= n <= 2100):
                return n
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
    custom_rect: dict[str, float] | list[dict[str, Any]] | None = None,
) -> list[tuple[str, bytes, dict[str, Any] | None]]:
    """Render a PDF page → N PNGs, one per zone.

    Retour : liste de ``(label, png_bytes)`` — un tuple par zone. Labels
    typiques :
      - ``"full" | "top" | "bottom"`` : mode preset (single zone)
      - ``"custom" | "<label-user>"``  : zone(s) custom user

    ``custom_rect`` accepts three shapes (in priority order) :
      * ``list[dict]`` : new multi-zone format
        ``[{x, y, w, h, rotation?, label?}, ...]`` — one output per zone,
        rotation applied per zone (0/90/180/270 clockwise) after render.
      * ``dict`` legacy : ``{x, y, w, h}`` — promoted to a single-element
        list internally.
      * ``None`` : fall back to ``crop_mode``.

    ``crop_mode`` (utilisé UNIQUEMENT si custom_rect est None/vide) :
      - ``"full"``      → [("full", ...)]
      - ``"top"``       → [("top", ...)]  ← quotidiens FR
      - ``"bottom"``    → [("bottom", ...)]  ← rare
      - ``"top_bottom"``→ [("top",...), ("bottom",...)]  ← robuste

    ``dpi`` : 200 = sweet spot minicpm-v:8b dans 8 Go VRAM.
    Raises IndexError when the page doesn't exist.
    """
    import fitz  # PyMuPDF

    # Normalise custom_rect into ``zones_norm`` — always a list of
    # dicts with (x, y, w, h, rotation, label) once fully resolved.
    zones_norm: list[dict[str, Any]] | None = None
    if custom_rect is not None:
        zones_norm = _normalise_crop_zones(custom_rect)

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

        # Résolution : (label, clip_rect, rotation_deg, zone_meta).
        # zone_meta = le dict full de la zone (avec tag/custom_tag)
        # pour les crops custom ; None pour les presets top/bottom/…
        renders: list[tuple[str, "fitz.Rect | None", int, dict[str, Any] | None]]
        if zones_norm:
            renders = []
            for idx, z in enumerate(zones_norm, 1):
                clip = fitz.Rect(
                    r.x0 + r.width * z["x"],
                    r.y0 + r.height * z["y"],
                    r.x0 + r.width * (z["x"] + z["w"]),
                    r.y0 + r.height * (z["y"] + z["h"]),
                )
                label = z.get("label") or f"custom{idx}"
                renders.append((label, clip, int(z.get("rotation") or 0), z))
        elif crop_mode == "top":
            renders = [("top", fitz.Rect(
                r.x0, r.y0, r.x1, r.y0 + r.height * 0.45,
            ), 0, None)]
        elif crop_mode == "bottom":
            renders = [("bottom", fitz.Rect(
                r.x0, r.y0 + r.height * 0.55, r.x1, r.y1,
            ), 0, None)]
        elif crop_mode == "top_bottom":
            renders = [
                ("top", fitz.Rect(
                    r.x0, r.y0, r.x1, r.y0 + r.height * 0.45,
                ), 0, None),
                ("bottom", fitz.Rect(
                    r.x0, r.y0 + r.height * 0.55, r.x1, r.y1,
                ), 0, None),
            ]
        else:  # "full" or unknown
            renders = [("full", None, 0, None)]

        # Cible : min 160 px sur la plus petite dimension du crop.
        # Une zone type "Date" à 1% de hauteur produit ~30 px à 260 DPI —
        # illisible pour minicpm-v. On boost le zoom par zone jusqu'à
        # atteindre le seuil, capé à 20× (PDF vectoriel = zoom safe,
        # le texte reste net). Cap max pour éviter des PNG > 4 MB.
        TARGET_MIN_PX = 160
        MAX_ZOOM = 20.0
        base_zoom = zoom

        out: list[tuple[str, bytes, dict[str, Any] | None]] = []
        for label, clip, rot, zone_meta in renders:
            local_zoom = base_zoom
            if clip is not None:
                pdf_w = max(1e-6, clip.width)
                pdf_h = max(1e-6, clip.height)
                px_w = pdf_w * base_zoom
                px_h = pdf_h * base_zoom
                shorter_px = min(px_w, px_h)
                if shorter_px < TARGET_MIN_PX:
                    boost = TARGET_MIN_PX / shorter_px
                    local_zoom = min(base_zoom * boost, MAX_ZOOM)
            # User upscale multiplier — appliqué EN PLUS du boost auto,
            # capé à MAX_ZOOM. Utile quand auto ne suffit pas sur du
            # texte fin (ex. « N° 26 290 » en 8 pt).
            user_up = 1.0
            if zone_meta and isinstance(zone_meta, dict):
                try:
                    user_up = max(1.0, min(4.0, float(zone_meta.get("upscale") or 1.0)))
                except (TypeError, ValueError):
                    user_up = 1.0
            if user_up > 1.001:
                local_zoom = min(local_zoom * user_up, MAX_ZOOM)
            local_matrix = fitz.Matrix(local_zoom, local_zoom)
            pix = page.get_pixmap(matrix=local_matrix, alpha=False, clip=clip)
            png_bytes = pix.tobytes(output="png")
            # Priorité 1 : rotation explicite user (multi-zone).
            if rot % 360 != 0:
                png_bytes = _rotate_png(png_bytes, rot)
            else:
                # Priorité 2 : bandeau très étroit → auto-rotate 90°
                # cw (safety net pour les crops verticaux tracés sans
                # rotation user — ex. tarif Paris Match).
                if pix.height >= pix.width * 3:
                    png_bytes = _rotate_png_90cw(png_bytes)
            out.append((label, png_bytes, zone_meta))
        return out
    finally:
        doc.close()


def _normalise_crop_zones(data: Any) -> list[dict[str, Any]] | None:
    """Parse the ``ai_crop_rect`` JSON blob into a normalised list.

    Accepts both shapes :
      - Legacy single dict : ``{x, y, w, h}`` → ``[{x, y, w, h, rotation:0}]``
      - New list of zones : ``[{x, y, w, h, rotation?, label?}, ...]``

    Coord fields are clamped to [0..1]. Zones missing any required
    field are dropped (never raised). Returns None when no valid
    zone survives — the caller falls back to global crop mode.
    """
    zones: list[dict[str, Any]] = []
    raw_zones: list[Any]
    if isinstance(data, list):
        raw_zones = data
    elif isinstance(data, dict):
        raw_zones = [data]
    else:
        return None
    for z in raw_zones:
        if not isinstance(z, dict):
            continue
        if not all(k in z for k in ("x", "y", "w", "h")):
            continue
        try:
            zone = {
                "x": max(0.0, min(1.0, float(z["x"]))),
                "y": max(0.0, min(1.0, float(z["y"]))),
                "w": max(0.01, min(1.0, float(z["w"]))),
                "h": max(0.01, min(1.0, float(z["h"]))),
                "rotation": int(z.get("rotation") or 0) % 360,
                "label": (z.get("label") or "").strip() or None,
                "tag": (z.get("tag") or "all"),
                "custom_tag": (z.get("custom_tag") or "").strip() or None,
                "upscale": max(1.0, min(4.0, float(z.get("upscale") or 1.0))),
            }
        except (TypeError, ValueError):
            continue
        # Clamp so (x + w) ≤ 1 and (y + h) ≤ 1 — protects PyMuPDF
        # against out-of-bounds Rect.
        zone["w"] = min(zone["w"], 1.0 - zone["x"])
        zone["h"] = min(zone["h"], 1.0 - zone["y"])
        zones.append(zone)
    return zones or None


def _has_extreme_aspect(png_bytes: bytes, max_ratio: float = 6.0) -> bool:
    """True when max(w,h) / min(w,h) exceeds ``max_ratio``.

    Cheap sanity check via PIL that returns False on any error (so a
    malformed PNG doesn't skip the vision by accident). Used to bypass
    the vision LLM on very thin strips (tarif vertical Paris Match,
    band bas de couverture) where minicpm-v produces garbage : the
    python OCR handles those zones better anyway.
    """
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(png_bytes)) as img:
            w, h = img.size
        short = min(w, h)
        long_ = max(w, h)
        if short <= 0:
            return False
        return (long_ / short) > max_ratio
    except Exception:  # noqa: BLE001
        return False


def _rotate_png_90cw(png_bytes: bytes) -> bytes:
    """Rotate a PNG 90° clockwise (shortcut for _rotate_png(..., 90))."""
    return _rotate_png(png_bytes, 90)


def _rotate_png(png_bytes: bytes, degrees: int) -> bytes:
    """Rotate a PNG by 90/180/270° clockwise via Pillow.

    Only cardinal rotations (0/90/180/270) — anything else is
    normalised via modulo. Falls back to the original bytes if
    Pillow chokes (should never happen, but keeps OCR usable).
    """
    deg = int(degrees) % 360
    if deg == 0:
        return png_bytes
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(png_bytes))
        # PIL rotate() is counter-clockwise → negate for clockwise UX.
        rotated = img.rotate(-deg, expand=True)
        buf = io.BytesIO()
        rotated.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        logger.warning("PNG rotation failed, sending original: %s", exc)
        return png_bytes


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
        # Chaque étape peut avoir son propre modèle (Settings → IA).
        # `effective_*` cascade sur `ai_text_model` quand la valeur
        # spécifique n'a pas été définie.
        torrent_model = cfg.effective_torrent_model
        arbiter_model = cfg.effective_arbiter_model
        vision_model = cfg.ai_vision_model
        available = await self._ollama.list_models()
        if not available:
            cb("skip", "Ollama injoignable — fallback parser natif")
            return await self._finalize_skip(run_id, steps, t0, "ollama_unreachable")
        torrent_available = torrent_model in available
        if not torrent_available:
            logger.info(
                "Torrent AI skipped — model %r absent from Ollama (or "
                "disabled). Pipeline continues with vision + python_ocr.",
                torrent_model,
            )

        # --- Guard 1bis : libère la VRAM des modèles concurrents -
        # Ollama peut être partagé avec un autre process qui a pinné
        # un modèle avec ``keep_alive=-1`` → notre vision ne pourrait
        # pas se charger et le call hangerait 5 min avant timeout.
        # On unload tout ce qui ne fait pas partie de notre pipeline.
        needed = {torrent_model, vision_model, arbiter_model} - {"__disabled__"}
        try:
            freed = await self._ollama.free_vram_for(needed)
            if freed:
                cb("switch", f"VRAM libérée (modèles concurrents : {', '.join(freed)})")
        except Exception as exc:  # noqa: BLE001
            logger.warning("VRAM free step failed non-fatally: %s", exc)

        # --- 1. Torrent-name LLM (skippé si modèle absent/désactivé) --
        if torrent_available:
            cb("text", f"Analyse nom torrent avec {torrent_model}")
            text_result, text_step = await self._call_json(
                model=torrent_model,
                prompt=(
                    f"{cfg.ai_text_prompt}\n\n---\nNom de fichier : "
                    f"{torrent_name}"
                ),
                step_name="text",
            )
            steps.append(text_step)
        else:
            # Fallback : parse basique via regex du torrent name pour
            # avoir au moins un candidat title/number côté « source 1 ».
            from app.parser.magazine_parser import parse_magazine_filename
            parsed = parse_magazine_filename(torrent_name)
            text_result = {
                "title": parsed.title,
                "issue_number": parsed.number,
                "year": parsed.year,
                "month": parsed.month,
                "day": parsed.day,
                "is_hs": parsed.is_special,
                "series_number": parsed.volume,
            }
            steps.append({
                "step": "text",
                "model": "deterministic-python (parser)",
                "input": {"torrent_name": torrent_name},
                "params": {"reason": "AI text disabled or model absent"},
                "output": text_result,
                "error": None,
                "elapsed_ms": 0,
            })
            cb("text", "Parser natif (IA texte désactivée)")

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

        # Source 3 déterministe (Python OCR) : collectée en parallèle
        # logique du vision LLM sur les MÊMES crops. Redondance qui
        # rattrape les échecs vision (loops, hallucinations) et
        # inversement (Tesseract râte souvent les textes stylisés).
        # Liste alimentée au fil des zones — un item par (page, zone).
        pyocr_outputs: list[dict[str, Any]] = []
        pyocr_enabled = bool(
            getattr(cfg, "ai_python_ocr_enabled", False)
            and pdf_path is not None
            and cfg.ai_enrichment_vision_pages
        )

        if has_vision:
            # --- 2. Switch : unload text, load vision ---------
            cb("switch", f"Chargement modèle vision {vision_model}…")
            await self._ollama.unload_model(torrent_model)

            pages = cfg.ai_enrichment_vision_pages or [1]
            crop_mode = getattr(cfg, "ai_enrichment_vision_crop", "full")
            # Custom rect prioritaire : l'user l'a défini visuellement
            # dans le UI Refresh IA → persisté sur Magazine.ai_crop_rect.
            custom_rect = await self._lookup_magazine_crop(magazine_id, issue_id)
            # Chaque page peut générer 1 ou 2 crops (top_bottom).
            # On les traite comme des appels vision distincts et on
            # laisse l'arbitre déterministe agréger.
            for idx, page_num in enumerate(pages, 1):
                try:
                    # DPI 260 pour un crop masthead (image petite en px),
                    # améliore la lisibilité des petits caractères type
                    # « N° 26 281 » sans faire exploser le budget VRAM
                    # minicpm-v:8b. DPI 200 en full-page (crop_mode=full)
                    # pour rester sous la limite contexte.
                    render_dpi = 260 if custom_rect else 200
                    rendered = _render_page_pngs(
                        pdf_path,
                        page_num,
                        dpi=render_dpi,
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
                        "model": vision_model,
                        "output": None,
                        "error": f"render_failed: {exc}",
                        "elapsed_ms": 0,
                    })
                    continue

                import base64
                for zone_label, png_bytes, zone_meta in rendered:
                    zone_tag = (zone_meta or {}).get("tag") or "all"
                    zone_custom_tag = (zone_meta or {}).get("custom_tag")
                    # Sauvegarde le crop réellement envoyé aux OCR :
                    # sert au rendu History (l'user voit l'image exacte
                    # utilisée pour chaque zone). Chemin relatif porté
                    # sur toutes les steps de la zone pour groupage UI.
                    crop_rel = _save_run_crop(
                        cfg, run_id, page_num, zone_label, png_bytes,
                    )
                    # --- 2bis. Python OCR (source déterministe) ------
                    # Sur la MÊME image que celle envoyée à la vision.
                    # Best-effort : jamais fatal — un échec (engine
                    # manquant, texte illisible) laisse simplement la
                    # source 3 vide et le pipeline continue.
                    pyocr_ok_len = 0  # utilisé + bas pour éventuel skip vision
                    if pyocr_enabled:
                        py_step = await self._run_python_ocr(
                            png_bytes,
                            engine_name=cfg.ai_python_ocr_engine,
                            page=page_num,
                            zone=zone_label,
                        )
                        py_step["tag"] = zone_tag
                        if zone_custom_tag:
                            py_step["custom_tag"] = zone_custom_tag
                        if crop_rel:
                            py_step["crop_file"] = crop_rel
                        if py_step.get("output"):
                            # Scrub + garbage check aussi côté Python OCR :
                            # Tesseract sort parfois du bruit style « 课影
                            # OUT » sur une image trop bruitée, qui
                            # polluerait l'arbiter Python (regex de date
                            # matcherait sur bruit).
                            raw_txt = _scrub_vision_text(py_step["output"])
                            garbage, reason = _is_vision_garbage({"raw_text": raw_txt})
                            if garbage:
                                py_step["garbage_dropped"] = reason
                                py_step["output"] = raw_txt  # affichée pour debug
                                logger.warning(
                                    "Python OCR garbage (page %s zone %s, %s) "
                                    "— output ignoré : %r",
                                    page_num, zone_label, reason, raw_txt[:120],
                                )
                            else:
                                py_step["output"] = raw_txt
                                pyocr_ok_len = len(raw_txt.strip())
                                pyocr_outputs.append({
                                    "page": page_num,
                                    "zone": zone_label,
                                    "tag": zone_tag,
                                    "engine": py_step.get("engine"),
                                    "raw_text": raw_txt,
                                })
                        steps.append(py_step)

                    # Skip vision si Python OCR a produit assez de texte
                    # propre pour cette zone (paramétrable via
                    # ai_vision_skip_if_pyocr_ge, 0 = never). Le VLM est
                    # souvent l'étape la plus lente (30-120 s/zone) et
                    # produit du bruit sur les crops petits que Tesseract
                    # sait déjà lire (Prix, Date, Numéro).
                    skip_threshold = getattr(cfg, "ai_vision_skip_if_pyocr_ge", 0) or 0
                    if skip_threshold > 0 and pyocr_ok_len >= skip_threshold:
                        steps.append({
                            "step": "vision",
                            "model": vision_model,
                            "page": page_num,
                            "zone": zone_label,
                            "tag": zone_tag,
                            "input": {"skipped": True},
                            "params": {
                                "skipped_reason": "python_ocr_sufficient",
                                "pyocr_len": pyocr_ok_len,
                                "threshold": skip_threshold,
                            },
                            "output": None,
                            "error": None,
                            "elapsed_ms": 0,
                        })
                        cb(
                            "vision",
                            f"Skip vision zone {zone_label} — python_ocr OK "
                            f"({pyocr_ok_len} chars ≥ {skip_threshold})",
                        )
                        continue

                    # --- 3. Vision LLM (toujours appelée) ------------
                    # User veut que TOUTES les étapes tournent pour
                    # que l'arbiter voie tout et décide. La perf n'est
                    # pas prioritaire : la qualité l'est.
                    # Le prompt est adapté selon le tag de la zone :
                    # "number" → ne cherche que le N°, "date" → date,
                    # etc. Zoom sur ce que l'utilisateur cible.
                    per_zone_prompt = _build_zone_vision_prompt(
                        base_prompt=cfg.ai_vision_prompt,
                        tag=zone_tag,
                        custom_tag=zone_custom_tag,
                    )
                    cb(
                        "vision",
                        f"OCR page {page_num} · zone {zone_label} "
                        f"[{zone_tag}] ({idx}/{len(pages)})",
                    )
                    img_b64 = base64.b64encode(png_bytes).decode("ascii")
                    vision_extras: dict[str, Any] = {
                        "page": page_num,
                        "zone": zone_label,
                        "tag": zone_tag,
                    }
                    if zone_custom_tag:
                        vision_extras["custom_tag"] = zone_custom_tag
                    if crop_rel:
                        vision_extras["crop_file"] = crop_rel
                    v_output, v_step = await self._call_json(
                        model=vision_model,
                        prompt=per_zone_prompt,
                        step_name="vision",
                        images_b64=[img_b64],
                        extra_step_fields=vision_extras,
                    )
                    steps.append(v_step)
                    if v_output is not None:
                        # Anti-garbage : rejette les sorties mojibake /
                        # CJK massif / caractères de contrôle / PUA /
                        # HTML tags / placeholders <TITRE>. Ces signaux
                        # sont nets — pas de faux positif.
                        garbage, reason = _is_vision_garbage(v_output)
                        if garbage:
                            logger.warning(
                                "Vision garbage detected (page %s zone %s, "
                                "%s) — vision output ignored : %r",
                                page_num, zone_label, reason, v_output,
                            )
                            v_step["garbage_dropped"] = reason
                            # Scrub aussi la sortie affichée en History
                            # pour ne pas exposer les kanji/PUA à l'user
                            # (rassure : « ma pipeline ne mange PAS ce
                            # bruit »). L'output reste dans le step pour
                            # debug mais nettoyé.
                            v_step["output"] = scrub_vision_output(v_output)
                            continue
                        # Anti-pollution soft : scrub les résidus (PUA
                        # isolé, tag html orphelin) qui ont passé le
                        # gate strict. Le résultat reste utilisable
                        # côté arbiter sans polluer les regex.
                        v_output = scrub_vision_output(v_output)
                        v_step["output"] = v_output
                        # Anti-leak : appliqué UNIQUEMENT sur les zones
                        # tagguées "title". Toute autre zone (Prix "38€",
                        # Date "20 Août", Numéro "N°26290", Sous-titre,
                        # ISSN, all=full-page, publisher, custom…) N'EST
                        # PAS censée contenir le titre magazine : le
                        # leak check trouverait 0 token commun et
                        # flaguerait faussement une sortie valide.
                        # Le garbage detector au-dessus catche déjà les
                        # vrais leaks minicpm-v (placeholders, PUA, HTML).
                        if zone_tag == "title":
                            expected_title = (
                                (text_result or {}).get("title") or ""
                            ).strip().lower()
                            if _is_vision_leak(v_output, expected_title):
                                logger.warning(
                                    "Vision leak detected (page %s zone %s) — "
                                    "vision output ignored : %r",
                                    page_num, zone_label,
                                    v_output,
                                )
                                v_step["leak_dropped"] = True
                                continue
                        vision_outputs.append({
                            "page": page_num,
                            "zone": zone_label,
                            "tag": zone_tag,
                            "data": v_output,
                        })

            # --- 4. Switch back to text model for arbiter -----
            cb("switch", f"Rechargement modèle arbitre {arbiter_model}…")
            await self._ollama.unload_model(vision_model)

        # --- 5. Arbitrage hybride : Python propose, LLM tranche ---
        # Architecture 3-couches :
        #   a) Python parse le raw_text vision avec regex → candidates
        #      (rapide, deterministic, mais peut manquer cas edge)
        #   b) LLM arbitre reçoit : torrent + vision_raw + python_candidates
        #      → choisit la valeur la plus réaliste par champ
        #   c) Post-validation Python : force torrent-primary sur les
        #      champs non-null torrent (l'IA ne peut PAS écraser)
        if vision_outputs or pyocr_outputs:
            cb("arbiter", "Analyse Python + arbitrage IA")
            arb_start = time.monotonic()

            # a) Python propose ses candidats depuis raw_text vision
            #    ET raw_text python_ocr : les 2 sources sont regroupées
            #    en un pool que la regex balaie ensemble → issue_number
            #    trouvé même si SEULE l'une des 2 le contient.
            python_candidates = _arbitrate(
                text_result or {},
                vision_outputs,
                pyocr_outputs=pyocr_outputs,
            )

            # b) LLM arbitre — voit les 4 sources et tranche.
            llm_final = None
            llm_err = None
            if arbiter_model in available:
                arb_prompt = _build_arbiter_prompt(
                    torrent=text_result or {},
                    vision_outputs=vision_outputs,
                    python_candidates=python_candidates,
                    base_prompt=cfg.ai_arbiter_prompt,
                    pyocr_outputs=pyocr_outputs,
                )
                llm_out, arb_step = await self._call_json(
                    model=arbiter_model,
                    prompt=arb_prompt,
                    step_name="arbiter",
                )
                steps.append(arb_step)
                if isinstance(llm_out, dict):
                    llm_final = llm_out
                else:
                    llm_err = arb_step.get("error") or "empty response"
            else:
                llm_err = f"arbiter model '{arbiter_model}' unavailable"

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
                    "input": {
                        "llm_final": llm_final,
                        "torrent": text_result,
                        "python_candidates": python_candidates,
                    },
                    "params": {
                        "torrent_primary": True,
                        "hallucination_threshold": 0.9,
                    },
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
        # Cleanup best-effort après finalize (jamais fatal).
        _cleanup_old_run_crops(cfg)
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

    async def _run_python_ocr(
        self,
        png_bytes: bytes,
        engine_name: str,
        page: int,
        zone: str,
    ) -> dict[str, Any]:
        """Run the configured python OCR engine on an image, best-effort.

        Runs the sync engine call in a thread so we don't block the
        event loop (Tesseract subprocess, EasyOCR PyTorch inference,
        RapidOCR ONNX all release the GIL enough for this to help).
        Never raises — engine errors surface as step["error"].
        """
        import asyncio

        t0 = time.monotonic()
        step: dict[str, Any] = {
            "step": "python_ocr",
            "engine": engine_name,
            "input": {
                "image_bytes": len(png_bytes),
                "image_kilobytes": round(len(png_bytes) / 1024, 1),
            },
            "params": {"engine": engine_name},
            "output": None,
            "error": None,
            "elapsed_ms": 0,
            "page": page,
            "zone": zone,
        }
        try:
            from app.services.python_ocr_service import (
                OCREngineError,
                get_engine,
            )
        except Exception as exc:  # noqa: BLE001
            step["error"] = f"python_ocr_service import failed: {exc}"
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            return step

        try:
            eng = get_engine(engine_name)
            text = await asyncio.to_thread(eng.read, png_bytes)
            step["output"] = text or ""
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        except OCREngineError as exc:
            step["error"] = str(exc)
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            logger.warning(
                "Python OCR (%s) failed on page %s zone %s: %s",
                engine_name, page, zone, exc,
            )
        except Exception as exc:  # noqa: BLE001
            step["error"] = f"unexpected: {exc}"
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            logger.warning(
                "Python OCR (%s) unexpected failure: %s", engine_name, exc,
            )
        return step

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
        # num_ctx : contexte Ollama pour vision. Une image PDF crop
        # zoomée peut consommer 4k-10k tokens vision.
        # - minicpm-v:8b : 8192 suffit (tient dans 8 Go VRAM)
        # - qwen2.5vl:7b : 16384 minimum sinon `unexpected EOF` HTTP
        #   500 côté Ollama (le modèle crash quand il déborde du ctx
        #   pendant l'encodage de l'image, sans même sortir 400).
        # 16384 est le safe upper bound qui tient dans 8 Go pour les
        # deux modèles. Au-dessus, minicpm-v peut OOM.
        if images_b64:
            num_ctx = 16384 if "qwen" in (model or "").lower() else 8192
        else:
            num_ctx = None
        # num_predict : plafond de génération vision. 800 était trop
        # court → minicpm-v tronquait à mi-chemin (« POLITAINE » =
        # fin de « MÉTROPOLITAINE »). 1500 laisse respirer titre +
        # sous-titre + petites lignes légales.
        num_predict = 1500 if images_b64 else None
        # repeat_penalty : 1.3 était trop agressif et créait des
        # boucles paradoxales (« N°\nN°\nPOLITAINE ») quand le modèle
        # évite tellement le token courant qu'il retombe dessus après
        # 2-3 tokens de filler. 1.1 casse les vraies loops sans
        # étouffer la répétition légitime d'un OCR (« BEL 4,40 € ·
        # LUX 4,40 € · SUI 5,90 CHF »).
        repeat_penalty = 1.1 if images_b64 else None
        # Structured input / params for the History drill-down. Un
        # step complet ressemble maintenant à :
        #   {step, input, params, output, error, elapsed_ms, ...extra}
        # - ``input`` : le contexte visible qui a nourri la step (prompt
        #   final, présence/taille de l'image, etc.)
        # - ``params`` : les knobs modèle (num_ctx, num_predict…)
        step: dict[str, Any] = {
            "step": step_name,
            "model": model,
            "input": {
                "prompt_len": len(prompt or ""),
                "prompt_preview": (prompt or "")[:400],
                "images": [
                    {"len_b64": len(b), "kilobytes": round(len(b) * 3 / 4 / 1024, 1)}
                    for b in (images_b64 or [])
                ],
            },
            "params": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "repeat_penalty": repeat_penalty,
                "temperature": 0.2,
            },
            "output": None,
            "error": None,
            "elapsed_ms": 0,
        }
        if extra_step_fields:
            step.update(extra_step_fields)
        try:
            out = await self._ollama.generate_json(
                model=model,
                prompt=prompt,
                images_b64=images_b64,
                num_ctx=num_ctx,
                num_predict=num_predict,
                repeat_penalty=repeat_penalty,
            )
            step["output"] = out
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            return out, step
        except OllamaError as exc:
            # Retry défensif : Ollama HTTP 500 « unexpected EOF » sur
            # vision = ctx trop petit pour digérer l'image. On retente
            # UNE fois avec un ctx doublé (jusqu'à 32k, plafond raisonnable
            # pour tenir dans 8 Go VRAM avec qwen2.5vl:7b).
            msg = str(exc)
            if images_b64 and "unexpected EOF" in msg and num_ctx and num_ctx < 32768:
                bumped_ctx = min(32768, (num_ctx or 8192) * 2)
                logger.warning(
                    "AI step %s crashed (unexpected EOF) — retry avec "
                    "num_ctx=%d (était %d)",
                    step_name, bumped_ctx, num_ctx,
                )
                try:
                    out = await self._ollama.generate_json(
                        model=model,
                        prompt=prompt,
                        images_b64=images_b64,
                        num_ctx=bumped_ctx,
                        num_predict=num_predict,
                        repeat_penalty=repeat_penalty,
                    )
                    step["params"]["num_ctx"] = bumped_ctx
                    step["params"]["retry_reason"] = "unexpected_eof"
                    step["output"] = out
                    step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
                    return out, step
                except OllamaError as exc2:
                    exc = exc2  # tombe dans le path d'échec ci-dessous
            step["error"] = str(exc)
            step["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            logger.warning("AI step %s failed: %s", step_name, exc)
            return None, step

    async def _lookup_magazine_crop(
        self,
        magazine_id: int | None,
        issue_id: int | None = None,
    ) -> list[dict[str, Any]] | None:
        """Charge la liste des zones custom pour l'issue cible.

        Le magazine stocke jusqu'à 3 sets (normal / weekend / hs) dans
        ai_crop_rect (JSON dict). Le pipeline sélectionne :
          - `hs` si issue.is_special=True
          - `weekend` si issue tombe sur un weekend_days consécutif
            regroupé (édition combinée)
          - `normal` sinon (défaut)
        Fallback vers `normal` si le set typé est vide.

        Rétro-compat : legacy single-list ou single-dict est traité
        comme `normal`.
        """
        if magazine_id is None:
            return None
        from sqlalchemy import select
        from app.models.magazine import Magazine
        from app.models.issue import Issue
        try:
            async with self._session_factory() as session:
                mag_row = (
                    await session.execute(
                        select(
                            Magazine.ai_crop_rect,
                            Magazine.weekend_days,
                        ).where(Magazine.id == magazine_id)
                    )
                ).first()
                if mag_row is None:
                    return None
                raw, weekend_days_str = mag_row[0], mag_row[1]
                if not raw:
                    return None
                data = json.loads(raw)

                # Détermine le type d'issue (normal / weekend / hs)
                issue_type = "normal"
                if issue_id is not None:
                    iss_row = (
                        await session.execute(
                            select(
                                Issue.is_special,
                                Issue.year,
                                Issue.month,
                                Issue.day,
                            ).where(Issue.id == issue_id)
                        )
                    ).first()
                    if iss_row is not None:
                        is_special, y, m, d = iss_row
                        if is_special:
                            issue_type = "hs"
                        elif weekend_days_str and y and m and d:
                            wd_set = set()
                            try:
                                wd_set = {
                                    int(x) for x in weekend_days_str.split(",")
                                    if x.strip()
                                }
                            except ValueError:
                                pass
                            if wd_set:
                                from datetime import date as _date
                                try:
                                    js_wd = _date(y, m, d).weekday()
                                    if js_wd in wd_set:
                                        issue_type = "weekend"
                                except ValueError:
                                    pass

                # Résolution du set à utiliser
                selected: list[Any] | None = None
                if isinstance(data, dict) and any(
                    k in data for k in ("normal", "weekend", "hs")
                ):
                    selected = data.get(issue_type) or data.get("normal") or []
                elif isinstance(data, (list, dict)):
                    # Legacy shape → tout est en `normal`
                    selected = data if isinstance(data, list) else [data]
                if not selected:
                    return None
                return _normalise_crop_zones(selected)
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
            row.steps_json = _safe_json_dumps(steps)
            row.final_json = _safe_json_dumps(final)
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
                        row.steps_json = _safe_json_dumps(steps)
                        row.final_json = _safe_json_dumps(final)
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


# Mois français → numéro (accents mixed, minuscule stripped).
_FR_MONTHS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "décembre": 12,
    "jan": 1, "fev": 2, "fév": 2, "mar": 3, "avr": 4,
    "jun": 6, "jui": 7, "juil": 7, "aou": 8, "aoû": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12, "déc": 12,
}


def _coerce_int_or_none(v: Any) -> int | None:
    """Retourne int(v) ou None. Tolère les strings de digits, les noms
    de mois français ('Août' → 8), et les tokens comme '25th' → 25."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):  # avant int, bool est subclass
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v.is_integer() else None
    if isinstance(v, str):
        s = v.strip().lower()
        if not s:
            return None
        # Nom de mois français ?
        if s in _FR_MONTHS:
            return _FR_MONTHS[s]
        # Digits (avec suffixe éventuel : "25th", "N°594")
        import re as _re
        m = _re.search(r"\d+", s)
        if m:
            try:
                return int(m.group(0))
            except ValueError:
                pass
    return None


def merge_ai_into_parsed(parsed, ai_final: dict[str, Any], mode: str) -> Any:
    """Apply AI extraction to a Parsed dataclass per autorité mode.

    ``parsed`` : the object returned by ``parse_magazine_filename``.
    Fields we override : title, number, year, month, day, is_hs
    (mapped to `is_special` on Issue downstream), series_number.

    Coercion int() automatique pour number / year / month / day —
    le vision LLM renvoie parfois "Août" au lieu de 8, ou "25th" au
    lieu de 25. Sans coerce, ces strings finissent stockées en DB
    comme text et cassent tout query numérique / template filename.

    ``mode`` :
      - ``remplace``  : any AI non-null value wins over parsed
      - ``complete``  : AI fills in only when parsed field is null
      - ``propose``   : parsed untouched (proposals table handles it)
      - anything else : no-op (defensive)
    """
    if mode in ("propose", "skipped_fallback") or not ai_final:
        return parsed

    # Champs numériques → coerce int (accept strings comme "Août"/"14th").
    numeric_map = {
        "issue_number": "number",
        "year": "year",
        "month": "month",
        "day": "day",
    }
    for ai_key, parsed_key in numeric_map.items():
        ai_val = ai_final.get(ai_key)
        if ai_val is None:
            continue
        coerced = _coerce_int_or_none(ai_val)
        if coerced is None:
            continue
        current = getattr(parsed, parsed_key, None)
        if mode == "remplace":
            setattr(parsed, parsed_key, coerced)
        elif mode == "complete" and current is None:
            setattr(parsed, parsed_key, coerced)

    # Champs string : title / subtitle / price / issn. Pas de coerce
    # numérique — juste strip + skip si vide.
    string_map = {
        "title": "title",
        "subtitle": "subtitle",
        "price": "price",
        "issn": "issn",
    }
    for ai_key, parsed_key in string_map.items():
        ai_val = ai_final.get(ai_key)
        if not (isinstance(ai_val, str) and ai_val.strip()):
            continue
        current = getattr(parsed, parsed_key, None)
        if mode == "remplace":
            setattr(parsed, parsed_key, ai_val.strip())
        elif mode == "complete" and not current:
            setattr(parsed, parsed_key, ai_val.strip())
    return parsed
