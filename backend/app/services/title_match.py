"""Titre release / magazine — scoring content-tokens Jaccard.

Utilisé par :
  - `wanted_search_service` : gate anti-off-topic AVANT le grab
    (compare le titre release Prowlarr vs le titre magazine)
  - `import_service` : gate anti-contamination APRÈS le download
    (compare le titre détecté par l'IA vision dans le PDF vs le
    titre magazine)

Approche : Jaccard sur tokens content-words, avec strip agressif
des mots noise (dates, formats, langues, mots génériques comme
« magazine »). Contourne les défauts de :
  - `fuzz.ratio` strict : trop punitif quand les longueurs diffèrent
  - `fuzz.WRatio` : trop permissif (matche des substrings)
  - Le parser (parsed_title incomplet)

Scoring : 100 × |common tokens| / |union tokens|.

Cas types :
  « Le Monde » vs « Le.Monde.Du.25.08.FR.PDF »        → 100 %
  « Le Monde » vs « Le.Monde.Diplomatique.Aout.2026 » →  50 %  (bloc)
  « Le Monde » vs « Le.Monde.du.Plein.Air.N200 »      →  25 %  (bloc)
  « Le Monde » vs « L.Equipe.24.08 »                  →   0 %  (bloc)
  « L'Équipe » vs « L.Equipe.24.08 »                  → 100 %
  « Paris Match » vs « Paris.Match.N1234.Aout.2026 »  → 100 %
  « Le Monde » vs « Le Monde des 30 et 31 Août »      → 100 %
"""
from __future__ import annotations

import re
import unicodedata

_STOP = {
    # Articles / prépositions FR/EN
    "le", "la", "les", "du", "de", "des", "un", "une", "au", "aux", "d", "l",
    "et", "ou", "the", "of", "and", "for", "in", "on", "at", "a", "an",
    # Codes langue
    "fr", "en", "de", "it", "es", "pt", "french", "english", "italian",
    # Formats
    "pdf", "epub", "mobi", "cbr", "cbz", "retail", "hq", "hd", "sd",
    "notag", "nogrp", "nopack", "ebook", "book", "complete",
    # Marqueurs édition (numéro, volume, tome — la valeur est un chiffre
    # stripé par le regex issue-number)
    "vol", "tome", "no", "num", "numero", "edition", "issue",
    # Mots ultra-génériques présents dans énormément de noms de magazines
    "magazine", "magasine", "journal", "revue", "hebdo", "mensuel",
    "weekly", "monthly", "daily", "special", "specials", "hs",
    "collector", "integrale",
    # Saisons (HS/spéciaux)
    "ete", "hiver", "printemps", "automne",
    "summer", "winter", "spring", "autumn", "fall",
}

_MONTH = {
    # Français long
    "janvier", "fevrier", "mars", "avril", "mai", "juin",
    "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
    # Français abbrev
    "jan", "fev", "fevr", "avr", "juil", "sept", "oct", "nov", "dec",
    # English long
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    # English abbrev
    "feb", "mar", "apr", "jun", "jul", "aug", "sep",
    # Jours FR abbrev + long
    "lun", "mar", "mer", "jeu", "ven", "sam", "dim",
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
    # Jours EN
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def content_tokens(txt: str) -> set[str]:
    """Tokens content-words significatifs : >=3 chars, non stop, non mois,
    pas 100 % chiffres, pas issue-number pattern.
    Accents strippés + lower + apostrophes/points normalisés."""
    out: set[str] = set()
    s = _strip_accents((txt or "").lower())
    # Apostrophes typographiques + curly + points → séparateur
    s = re.sub(r"[''`.]", " ", s)
    # Strip patterns issue-number : N1234, N°1234, #1234, No1234, num1234,
    # vol1234, tome1234 (chiffres accolés ou séparés par espace).
    s = re.sub(
        r"\b(?:n[o°]?|num|numero|vol|tome|t|#)\s*\d+\b",
        " ", s,
    )
    for w in re.findall(r"[a-z0-9À-ÿ]+", s):
        if len(w) < 3:
            continue
        if w in _STOP or w in _MONTH:
            continue
        if w.isdigit():
            continue
        # Rejette tokens alphanumériques dominés par digits (n1234, hd1080p)
        _digits = sum(1 for c in w if c.isdigit())
        if _digits > len(w) // 2:
            continue
        out.add(w)
    return out


def title_match_score(candidate: str, magazine_title: str) -> float:
    """Score Jaccard content-tokens 0-100.

    100 = tous les mots content du magazine sont dans candidate ET
    inversement (aucun mot supplémentaire suspect).
    0 = aucun mot commun.
    """
    if not candidate or not magazine_title:
        return 0.0
    mag = content_tokens(magazine_title)
    if not mag:
        # Titre magazine composé UNIQUEMENT de stop-words / mois : fallback
        # sur ratio strict pour éviter division par zéro.
        from rapidfuzz import fuzz as _fz
        return float(_fz.ratio(candidate.lower(), magazine_title.lower()))
    cand = content_tokens(candidate)
    common = mag & cand
    union = mag | cand
    if not union:
        return 0.0
    return 100.0 * len(common) / len(union)
