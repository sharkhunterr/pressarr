"""Smart RSS matching service with multi-criteria scoring and pattern learning."""
import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.history import History
from app.models.issue import Issue
from app.models.magazine import Magazine
from app.models.magazine_pattern import MagazinePattern
from app.models.magazine_rule import MagazineRule
from app.parser.magazine_parser import (
    ParseResult,
    fuzzy_match_title,
    normalize_title,
    parse_magazine_filename,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------


@dataclass
class MatchWeights:
    """Configurable scoring weights for RSS matching."""

    title_match: float = 50.0       # Max points for title similarity
    search_terms_match: float = 50.0  # Alternative to title (takes the best)
    number_match: float = 25.0      # Points for matching a wanted issue by number
    date_match: float = 20.0        # Points for matching by year+month
    pattern_bonus: float = 25.0     # Bonus for matching a learned naming pattern
    language_match: float = 5.0     # Bonus for matching expected language
    quality_bonus: float = 5.0      # Bonus for a recognized quality tag
    title_threshold: float = 85.0   # Minimum fuzzy match % for title (prevents false positives)
    min_threshold: float = 70.0     # Minimum score to accept a match


@dataclass
class MatchResult:
    """Result of smart matching an RSS item against a magazine."""

    magazine: Magazine
    issue: Issue | None
    score: float
    matched_via: str  # "title", "search_terms", "pattern"
    details: str = ""


@dataclass
class NamingPattern:
    """A naming pattern extracted from past grabs."""

    magazine_id: int
    template: str           # e.g. "Science.et.Vie.N.{number}.French.PDF"
    title_variant: str      # e.g. "Science.et.Vie"
    language: str | None
    example_title: str


# ---------------------------------------------------------------------------
# Pattern extraction
# ---------------------------------------------------------------------------

# Patterns for issue number replacement (order matters — try specific first)
_NUMBER_PATTERNS = [
    (r"([Nn][\s.]?)\d+", r"\g<1>{number}"),
    (r"(#)\d+", r"\g<1>{number}"),
    (r"([Ii]ssue\s+)\d+", r"\g<1>{number}"),
    (r"([Nn]o\.?\s*)\d+", r"\g<1>{number}"),
    (r"([Nn]um[eé]ro\s+)\d+", r"\g<1>{number}"),
    (r"([Nn]r\.?\s*)\d+", r"\g<1>{number}"),
    (r"([Hh]eft\s+)\d+", r"\g<1>{number}"),         # German
    (r"([Nn][uú]mero\s+)\d+", r"\g<1>{number}"),     # Spanish/Italian
    # Bare trailing number (last resort)
    (r"(\s)\d+$", r"\g<1>{number}"),
]


def extract_naming_pattern(release_title: str, parsed: ParseResult) -> str | None:
    """Build a naming template from a grabbed release title.

    Replaces the specific issue number, year, month, and day with
    placeholders so that future releases with a different number/date
    can be matched against the same template.

    Returns *None* when no substitution was possible.
    """
    if not release_title:
        return None

    template = release_title

    # Replace issue number
    if parsed.number is not None:
        num_str = str(parsed.number)
        replaced = False
        for pat, repl in _NUMBER_PATTERNS:
            # Build a specific regex that matches the actual number
            specific_pat = pat.replace(r"\d+", re.escape(num_str))
            new_template = re.sub(specific_pat, repl, template, count=1)
            if new_template != template:
                template = new_template
                replaced = True
                break
        # If none of the named patterns matched, try a raw replacement
        if not replaced:
            template = template.replace(num_str, "{number}", 1)

    # Replace year
    if parsed.year is not None:
        template = template.replace(str(parsed.year), "{year}", 1)

    # Replace month (two-digit)
    if parsed.month is not None:
        month_2d = f"{parsed.month:02d}"
        if month_2d in template:
            template = template.replace(month_2d, "{month}", 1)

    # Replace day (two-digit)
    if parsed.day is not None:
        day_2d = f"{parsed.day:02d}"
        if day_2d in template:
            template = template.replace(day_2d, "{day}", 1)

    if template == release_title:
        return None

    return template


def match_against_pattern(
    release_title: str,
    parsed: ParseResult,
    pattern: NamingPattern,
) -> float:
    """Score how well *release_title* matches a learned *pattern*.

    Returns a value between 0.0 (no match) and 1.0 (exact structural match).
    """
    template = pattern.template

    # Build regex from template: escape everything, then open up placeholders
    regex_str = re.escape(template)
    regex_str = regex_str.replace(re.escape("{number}"), r"\d+")
    regex_str = regex_str.replace(re.escape("{year}"), r"\d{4}")
    regex_str = regex_str.replace(re.escape("{month}"), r"\d{1,2}")
    regex_str = regex_str.replace(re.escape("{day}"), r"\d{1,2}")

    try:
        if re.fullmatch(regex_str, release_title, re.IGNORECASE):
            return 1.0
    except re.error:
        pass

    # Partial match: compare title portions
    title_variant_norm = normalize_title(pattern.title_variant)
    parsed_norm = normalize_title(parsed.title) if parsed.title else ""
    if title_variant_norm and parsed_norm:
        from rapidfuzz.fuzz import WRatio

        ratio = WRatio(title_variant_norm, parsed_norm)
        if ratio >= 85.0:
            return ratio / 100.0 * 0.7  # Scale down for partial

    return 0.0


# ---------------------------------------------------------------------------
# Pattern cache
# ---------------------------------------------------------------------------

_pattern_cache: dict[int, list[NamingPattern]] = {}


async def load_patterns_for_magazine(
    db: AsyncSession,
    magazine_id: int,
) -> list[NamingPattern]:
    """Load naming patterns from past grab events for a magazine (cached)."""
    if magazine_id in _pattern_cache:
        return _pattern_cache[magazine_id]

    result = await db.execute(
        select(History).where(
            History.magazine_id == magazine_id,
            History.event_type == "grab",
        ).order_by(History.date.desc()).limit(50)
    )
    events = result.scalars().all()

    patterns: list[NamingPattern] = []
    seen_templates: set[str] = set()

    for event in events:
        if not event.details:
            continue
        # Extract the release title from details
        release_title = event.details
        for prefix in (
            "Grabbed: ",
            "Grabbed from Internet Archive: ",
            "Grabbed from Anna's Archive: ",
        ):
            if release_title.startswith(prefix):
                release_title = release_title[len(prefix):]
                break

        parsed = parse_magazine_filename(release_title)
        template = extract_naming_pattern(release_title, parsed)
        if template and template not in seen_templates:
            seen_templates.add(template)

            title_variant = parsed.title or ""
            if not title_variant:
                idx = template.find("{")
                if idx > 0:
                    title_variant = template[:idx].rstrip(". -_")

            patterns.append(NamingPattern(
                magazine_id=magazine_id,
                template=template,
                title_variant=title_variant,
                language=parsed.language if parsed.language != "unknown" else None,
                example_title=release_title,
            ))

    # Also load user-defined patterns from MagazinePattern table
    user_result = await db.execute(
        select(MagazinePattern).where(
            MagazinePattern.magazine_id == magazine_id
        )
    )
    for up in user_result.scalars().all():
        parsed = parse_magazine_filename(up.pattern)
        template = extract_naming_pattern(up.pattern, parsed)
        if template and template not in seen_templates:
            seen_templates.add(template)
            title_variant = parsed.title or ""
            if not title_variant:
                idx = template.find("{")
                if idx > 0:
                    title_variant = template[:idx].rstrip(". -_")
            patterns.append(NamingPattern(
                magazine_id=magazine_id,
                template=template,
                title_variant=title_variant,
                language=parsed.language if parsed.language != "unknown" else None,
                example_title=up.pattern,
            ))

    _pattern_cache[magazine_id] = patterns
    return patterns


def invalidate_pattern_cache(magazine_id: int | None = None) -> None:
    """Invalidate the pattern cache (call after a new grab)."""
    if magazine_id is not None:
        _pattern_cache.pop(magazine_id, None)
    else:
        _pattern_cache.clear()


# ---------------------------------------------------------------------------
# Country → expected language mapping
# ---------------------------------------------------------------------------

_COUNTRY_LANG: dict[str, str] = {
    "FR": "french",
    "US": "english",
    "GB": "english",
    "CA": "english",
    "AU": "english",
    "DE": "german",
    "AT": "german",
    "CH": "german",
    "ES": "spanish",
    "MX": "spanish",
    "IT": "italian",
    "PT": "portuguese",
    "BR": "portuguese",
    "NL": "dutch",
    "BE": "french",
    "JP": "japanese",
    "RU": "russian",
}


# ---------------------------------------------------------------------------
# Main matching function
# ---------------------------------------------------------------------------


async def smart_match_rss_item(
    db: AsyncSession,
    rss_title: str,
    magazines: list[Magazine],
    weights: MatchWeights | None = None,
    wanted_by_number: dict[tuple[int, int], Issue] | None = None,
    wanted_by_date: dict[tuple[int, int, int], Issue] | None = None,
) -> MatchResult | None:
    """Score an RSS item against all monitored magazines.

    *wanted_by_number* and *wanted_by_date* are pre-loaded lookup dicts
    to avoid per-item DB queries.  Keys are ``(magazine_id, number)`` and
    ``(magazine_id, year, month)`` respectively.

    Returns the best :class:`MatchResult` above the threshold, or *None*.
    """
    if weights is None:
        weights = MatchWeights()

    parsed = parse_magazine_filename(rss_title)
    if not parsed.title:
        return None

    best: MatchResult | None = None

    for magazine in magazines:
        # --- 0. Apply include/exclude rules (hard filter) ---
        rules: list[MagazineRule] = []
        if hasattr(magazine, "rules") and magazine.rules is not None:
            rules = magazine.rules
        else:
            rules_result = await db.execute(
                select(MagazineRule).where(
                    MagazineRule.magazine_id == magazine.id
                )
            )
            rules = list(rules_result.scalars().all())

        if rules:
            from app.services.magazine_service import apply_magazine_rules

            excluded, _reason = apply_magazine_rules(rss_title, rules)
            if excluded:
                continue

        score = 0.0
        matched_via = ""
        details_parts: list[str] = []

        # --- 1. Title fuzzy match ---
        title_score = 0.0
        title_match = fuzzy_match_title(
            parsed.title,
            [magazine.title],
            threshold=weights.title_threshold,
        )
        if title_match:
            _, fuzzy_pct = title_match
            title_score = (fuzzy_pct / 100.0) * weights.title_match
            score += title_score
            matched_via = "title"
            details_parts.append(f"title={fuzzy_pct:.0f}%")

        # --- 1b. search_terms match (use the better of title vs search_terms) ---
        if magazine.search_terms:
            terms = [t.strip() for t in magazine.search_terms.split(",") if t.strip()]
            if terms:
                st_match = fuzzy_match_title(
                    parsed.title,
                    terms,
                    threshold=weights.title_threshold,
                )
                if st_match:
                    _, st_pct = st_match
                    st_points = (st_pct / 100.0) * weights.search_terms_match
                    if st_points > title_score:
                        score = score - title_score + st_points
                        title_score = st_points
                        matched_via = "search_terms"
                        details_parts.append(f"search_terms={st_pct:.0f}%")

        # If neither title nor search_terms produced any score, skip
        if score == 0.0:
            continue

        # --- 2. Pattern matching (learned from past grabs) ---
        patterns = await load_patterns_for_magazine(db, magazine.id)
        if patterns:
            best_pattern_score = 0.0
            for pattern in patterns:
                p_score = match_against_pattern(rss_title, parsed, pattern)
                if p_score > best_pattern_score:
                    best_pattern_score = p_score
            if best_pattern_score > 0.0:
                score += best_pattern_score * weights.pattern_bonus
                details_parts.append(f"pattern={best_pattern_score:.0%}")

        # --- 3. Issue number or date match ---
        issue: Issue | None = None

        if parsed.number is not None and wanted_by_number is not None:
            issue = wanted_by_number.get((magazine.id, parsed.number))
            if issue:
                score += weights.number_match
                details_parts.append("number_match")

        if (
            issue is None
            and parsed.year is not None
            and parsed.month is not None
            and wanted_by_date is not None
        ):
            issue = wanted_by_date.get((magazine.id, parsed.year, parsed.month))
            if issue:
                score += weights.date_match
                details_parts.append("date_match")

        # A match without a specific wanted issue is not actionable
        if issue is None:
            continue

        # --- 4. Language match bonus ---
        if parsed.language != "unknown":
            expected_lang = _COUNTRY_LANG.get(
                (magazine.country or "").upper()
            )
            if expected_lang and parsed.language == expected_lang:
                score += weights.language_match
                details_parts.append("lang_match")

        # --- 5. Quality tag bonus ---
        if parsed.quality != "unknown":
            score += weights.quality_bonus
            details_parts.append(f"quality={parsed.quality}")

        # --- Threshold check ---
        if score >= weights.min_threshold:
            result = MatchResult(
                magazine=magazine,
                issue=issue,
                score=score,
                matched_via=matched_via,
                details=", ".join(details_parts),
            )
            if best is None or score > best.score:
                best = result

    return best
