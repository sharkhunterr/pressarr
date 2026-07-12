"""Shared HTML / URL helpers for the scene magazine indexers.

The two providers we ship (Bookys, telecharger-magazines.org)
both publish DataLife Engine -style article pages with hoster
links scattered through the article body. The functions here
centralise the "is this URL a known file-hoster?" decision and
a couple of best-effort title parsers so each scraper stays
small and focused on its own site quirks.
"""

import re
from urllib.parse import urlparse

# Bare host suffixes the operator likely uses with JDownloader 2.
# Order matters only for the rendered "hoster" badge — the longer
# (more specific) ones are matched first.
KNOWN_HOSTERS: tuple[str, ...] = (
    "1fichier.com",
    "rapidgator.net",
    "rapidgator.asia",
    "uploaded.net",
    "uploaded.to",
    "ul.to",
    "nitroflare.com",
    "turbobit.net",
    "turb.cc",
    "katfile.com",
    "ddownload.com",
    "fikper.com",
    "mexa.sh",
    "mega.nz",
    "mega.co.nz",
    "send.cm",
    "filerice.com",
    "easybytez.com",
    "mediafire.com",
    "uploadrar.com",
    "uploady.io",
    "k2s.cc",
    "keep2share.cc",
    "filefactory.com",
    "filestore.to",
    "letsupload.io",
    "drop.download",
    "drop.lk",
    # Seen in the wild on telecharger-magazines.org via
    # liens-direct.com — most are JDownloader-compatible.
    "frdl.io",
    "upfiles.com",
    "dailyuploads.net",
    "jioupload.top",
    "filespayouts.com",
    "filespay.com",
)


def detect_hoster(url: str) -> str | None:
    """Return the canonical hoster slug for ``url`` or None when
    it doesn't match any known file-hoster (so navigation,
    pagination and social links are filtered out before
    persistence)."""
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return None
    host = host.lower().lstrip("www.")
    for h in KNOWN_HOSTERS:
        if host == h or host.endswith("." + h):
            return h
    return None


_ISSUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "N°123", "n° 123", "no 123", "# 123"
    re.compile(r"\bn[°ºo]?\s*(\d{1,4})\b", re.IGNORECASE),
    # "Numéro 123", "Numero 123"
    re.compile(r"\bnum[ée]ro\s*(\d{1,4})\b", re.IGNORECASE),
    # "HS 4", "Hors-Série 4", "Hors Serie 4"
    re.compile(r"\bhors[- ]?s[ée]rie\s*(\d{1,4})\b", re.IGNORECASE),
    re.compile(r"\bhs\s*(\d{1,4})\b", re.IGNORECASE),
    # "#42", "Issue 42"
    re.compile(r"\bissue\s*(\d{1,4})\b", re.IGNORECASE),
    re.compile(r"#\s*(\d{1,4})\b"),
)


def parse_issue_label(title: str) -> str | None:
    """Cheap "what issue is this?" heuristic. The returned label
    is the operator-facing string (with the matched prefix), not
    just the raw number, so "N°123" and "Issue 123" stay
    distinct in the UI."""
    if not title:
        return None
    for pat in _ISSUE_PATTERNS:
        m = pat.search(title)
        if m:
            return m.group(0).strip()
    return None


_YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def parse_year(title: str) -> int | None:
    """Pull the first plausible-looking 4-digit year out of the
    title. Bounded so junk like 1234 in an issue number doesn't
    register."""
    if not title:
        return None
    m = _YEAR_RE.search(title)
    return int(m.group(1)) if m else None


_SIZE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(GB|MB|KB|Go|Mo|Ko)", re.IGNORECASE
)


def parse_size_bytes(text: str | None) -> int | None:
    """Parse "12.4 MB" / "1,2 Go" / "847 Ko" → bytes. None on
    miss. Tolerates the French comma decimal."""
    if not text:
        return None
    m = _SIZE_RE.search(text)
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    unit = m.group(2).lower()
    if unit in ("gb", "go"):
        return int(value * 1024 * 1024 * 1024)
    if unit in ("mb", "mo"):
        return int(value * 1024 * 1024)
    if unit in ("kb", "ko"):
        return int(value * 1024)
    return None


_FORMAT_RE = re.compile(
    r"\b(pdf|epub|cbz|cbr|mobi|azw3)\b", re.IGNORECASE
)


def parse_format(title: str | None) -> str | None:
    """Lower-case file-format label from the title. Most
    scraped magazines are PDF — this catches the rare exception."""
    if not title:
        return None
    m = _FORMAT_RE.search(title)
    return m.group(1).lower() if m else None
