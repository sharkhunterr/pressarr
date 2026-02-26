from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Month lookup tables (multilingual, case-insensitive)
# ---------------------------------------------------------------------------

MONTH_NAMES: dict[str, int] = {}

_MONTH_DATA: dict[str, list[str]] = {
    # English
    "en": [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    ],
    # French
    "fr": [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ],
    # German
    "de": [
        "januar", "februar", "märz", "april", "mai", "juni",
        "juli", "august", "september", "oktober", "november", "dezember",
    ],
    # Spanish
    "es": [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ],
    # Italian
    "it": [
        "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    ],
}

# 3-letter abbreviations per language
_MONTH_ABBREVS: dict[str, list[str]] = {
    "en": [
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    ],
    "fr": [
        "jan", "fév", "mar", "avr", "mai", "jun",
        "jul", "aoû", "sep", "oct", "nov", "déc",
    ],
    "de": [
        "jan", "feb", "mär", "apr", "mai", "jun",
        "jul", "aug", "sep", "okt", "nov", "dez",
    ],
    "es": [
        "ene", "feb", "mar", "abr", "may", "jun",
        "jul", "ago", "sep", "oct", "nov", "dic",
    ],
    "it": [
        "gen", "feb", "mar", "apr", "mag", "giu",
        "lug", "ago", "set", "ott", "nov", "dic",
    ],
}


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _build_month_lookup() -> dict[str, int]:
    lookup: dict[str, int] = {}
    for _lang, names in _MONTH_DATA.items():
        for idx, name in enumerate(names, start=1):
            lookup[name.lower()] = idx
            stripped = _strip_accents(name.lower())
            if stripped != name.lower():
                lookup[stripped] = idx
    for _lang, abbrevs in _MONTH_ABBREVS.items():
        for idx, abbr in enumerate(abbrevs, start=1):
            lookup[abbr.lower()] = idx
            stripped = _strip_accents(abbr.lower())
            if stripped != abbr.lower():
                lookup[stripped] = idx
    return lookup


MONTH_NAMES = _build_month_lookup()

# ---------------------------------------------------------------------------
# Quality mapping
# ---------------------------------------------------------------------------

_QUALITY_MAP: dict[str, str] = {
    "truepdf": "truepdf",
    "true pdf": "truepdf",
    "retail": "retail",
    "scan": "scan",
    "hq": "pdf_hq",
    "pdf-hq": "pdf_hq",
    "pdf hq": "pdf_hq",
    "high quality": "pdf_hq",
    "lq": "pdf_lq",
    "pdf-lq": "pdf_lq",
    "pdf lq": "pdf_lq",
    "low quality": "pdf_lq",
}

# ---------------------------------------------------------------------------
# Language mapping
# ---------------------------------------------------------------------------

_LANGUAGE_MAP: dict[str, str] = {
    "french": "french",
    "fr": "french",
    "english": "english",
    "en": "english",
    "german": "german",
    "de": "german",
    "spanish": "spanish",
    "es": "spanish",
    "italian": "italian",
    "it": "italian",
    "multi": "multi",
}

# ---------------------------------------------------------------------------
# Supported extensions
# ---------------------------------------------------------------------------

_EXTENSIONS: set[str] = {"pdf", "epub", "cbr", "cbz"}

# ---------------------------------------------------------------------------
# ParseResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class ParseResult:
    title: str = ""
    number: int | None = None
    volume: int | None = None
    year: int | None = None
    month: int | None = None
    language: str = "unknown"
    quality: str = "unknown"
    format: str = "unknown"
    is_special: bool = False
    release_group: str | None = None
    raw_filename: str = ""


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

# Pre-compiled regexes
_RE_EXTENSION = re.compile(r"\.(" + "|".join(_EXTENSIONS) + r")$", re.IGNORECASE)

# Release group: text in parentheses or square brackets at the very end
_RE_RELEASE_GROUP = re.compile(r"[\(\[]\s*([^\)\]]+?)\s*[\)\]]\s*$")

# Quality keywords pattern (order matters: longer first)
_QUALITY_KEYWORDS = sorted(_QUALITY_MAP.keys(), key=len, reverse=True)
_RE_QUALITY = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _QUALITY_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Language keywords pattern
_LANG_KEYWORDS = sorted(_LANGUAGE_MAP.keys(), key=len, reverse=True)
_RE_LANGUAGE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _LANG_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Hors-serie / special markers
_RE_SPECIAL = re.compile(
    r"\b(hors[\s-]?s[eé]rie|hs|sp[eé]cial|special)\b",
    re.IGNORECASE,
)

# Issue number patterns (order matters)
_RE_ISSUE = re.compile(
    r"(?:"
    r"[Nn][\s.]?(\d+)(?:\s*[-–]\s*(\d+))?"  # N1285, N 1285, N.1285, N1285-1286
    r"|[Ii]ssue\s+(\d+)"                      # Issue 12
    r"|#(\d+)"                                 # #42
    r"|[Nn][oO]\.?\s*(\d+)"                    # No.5, No 5
    r"|[Nn]um[eé]ro\s+(\d+)"                   # Numero 10
    r"|[Nn]r\.?\s*(\d+)"                        # Nr.5, Nr 5
    r")",
    re.IGNORECASE,
)

# Volume patterns
_RE_VOLUME = re.compile(
    r"(?:"
    r"[Vv]ol(?:ume)?\.?\s*(\d+)"   # Vol.3, Volume 5, Vol 3
    r"|[Vv](\d+)"                   # V2
    r")",
    re.IGNORECASE,
)

# Year-month pattern: 2025-03 or 2025/03
_RE_YEAR_MONTH = re.compile(r"\b((?:19|20)\d{2})[-/](0[1-9]|1[0-2])\b")

# Standalone year
_RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

# Month name pattern built from the lookup keys (sorted longest first to
# prevent partial matches).
_month_keys_sorted = sorted(MONTH_NAMES.keys(), key=len, reverse=True)
_RE_MONTH_NAME = re.compile(
    r"\b(" + "|".join(re.escape(m) for m in _month_keys_sorted) + r")\b",
    re.IGNORECASE,
)


def _normalize_separators(text: str) -> str:
    # Replace underscores with spaces
    text = text.replace("_", " ")
    # Replace dots unless between two digits (preserve "3.5" style numbers)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _consume(text: str, pattern: re.Pattern[str]) -> tuple[str, re.Match[str] | None]:
    m = pattern.search(text)
    if m:
        text = text[:m.start()] + " " + text[m.end():]
        text = re.sub(r"\s+", " ", text).strip()
    return text, m


def parse_magazine_filename(filename: str) -> ParseResult:
    result = ParseResult(raw_filename=filename)

    try:
        working = filename

        # 1. Remove extension and detect format
        ext_match = _RE_EXTENSION.search(working)
        if ext_match:
            result.format = ext_match.group(1).lower()
            working = working[:ext_match.start()]

        # 2. Normalize separators
        working = _normalize_separators(working)

        # 3. Extract release group (parentheses/brackets at end)
        rg_match = _RE_RELEASE_GROUP.search(working)
        if rg_match:
            result.release_group = rg_match.group(1).strip()
            working = working[:rg_match.start()].strip()

        # 4. Extract quality keywords
        working, q_match = _consume(working, _RE_QUALITY)
        if q_match:
            result.quality = _QUALITY_MAP[q_match.group(1).lower()]

        # 5. Extract language keywords
        #    We need to be careful not to match language codes that are part
        #    of month abbreviations (e.g., "mai" should not match "it").
        #    Process on a working copy; search from longest keyword first.
        working, l_match = _consume(working, _RE_LANGUAGE)
        if l_match:
            result.language = _LANGUAGE_MAP[l_match.group(1).lower()]

        # 6. Extract hors-serie markers
        working, s_match = _consume(working, _RE_SPECIAL)
        if s_match:
            result.is_special = True

        # 7. Extract issue number
        working, i_match = _consume(working, _RE_ISSUE)
        if i_match:
            # Find the first non-None group
            for g in i_match.groups():
                if g is not None:
                    result.number = int(g)
                    break

        # 8. Extract volume
        working, v_match = _consume(working, _RE_VOLUME)
        if v_match:
            for g in v_match.groups():
                if g is not None:
                    result.volume = int(g)
                    break

        # 9. Extract date
        # Try year-month format first (2025-03)
        working, ym_match = _consume(working, _RE_YEAR_MONTH)
        if ym_match:
            result.year = int(ym_match.group(1))
            result.month = int(ym_match.group(2))
        else:
            # Extract year first (standalone 4-digit year)
            working, y_match = _consume(working, _RE_YEAR)
            if y_match:
                result.year = int(y_match.group(1))

            # Only try month name extraction if a year was found
            # (prevents false matches like "Mag" → Italian May)
            if result.year is not None:
                working_lower = working.lower()
                mn_match = _RE_MONTH_NAME.search(working_lower)
                if mn_match:
                    month_str = mn_match.group(1).lower()
                    month_val = MONTH_NAMES.get(month_str) or MONTH_NAMES.get(
                        _strip_accents(month_str)
                    )
                    if month_val:
                        result.month = month_val
                        working = (
                            working[:mn_match.start()]
                            + " "
                            + working[mn_match.end():]
                        )
                        working = re.sub(r"\s+", " ", working).strip()

        # 10. Remaining tokens = title
        # Clean up dashes/hyphens at boundaries
        title = working.strip(" -–")
        # Collapse whitespace
        title = re.sub(r"\s+", " ", title).strip()
        result.title = title

    except Exception:
        # Parser should never crash on malformed input
        pass

    return result


# ---------------------------------------------------------------------------
# Fuzzy title matching
# ---------------------------------------------------------------------------


def normalize_title(title: str) -> str:
    text = title.lower()
    # Strip accents
    text = _strip_accents(text)
    # Remove articles (French and English)
    text = re.sub(r"\b(le|la|les|l'|the|a|an)\b", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fuzzy_match_title(
    parsed_title: str,
    known_titles: list[str],
    threshold: float = 80.0,
) -> tuple[str, float] | None:
    from rapidfuzz import process
    from rapidfuzz.fuzz import WRatio

    if not parsed_title or not known_titles:
        return None

    normalized_parsed = normalize_title(parsed_title)
    normalized_known = {normalize_title(t): t for t in known_titles}

    result = process.extractOne(
        normalized_parsed,
        list(normalized_known.keys()),
        scorer=WRatio,
    )
    if result is None:
        return None

    best_norm, score, _idx = result
    if score >= threshold:
        return normalized_known[best_norm], score
    return None
