"""Wanted-issue search pipeline.

Orchestre la recherche par issue "wanted" avec un pipeline unifié :

  1. Query build : `magazine.title + N{number}` OU `magazine.title + YYYY MM (DD)`.
  2. Fetch : appelle Prowlarr sur tous les indexers activés + groupes de
     catégories issus des overrides magazine.
  3. Parse + Python score : `search_service.score_release` (fuzzy title +
     quality + size + seeds + age) → score 0-100 par candidat.
  4. Rules : `magazine_service.apply_magazine_rules` sur `parsed.title +
     filename`. Les exclusions sont retirées de la sélection, les inclusions
     restent (les rules include ne boostent pas le score — elles gatekeep).
  5. Blocklist : cache local — un release blocklisté est retiré aussi.
  6. IA batch + arbiter : si `config.ai_ranker_enabled`, lance
     `ai_ranker_service.rank()` sur les top-K survivants. Renvoie un
     `RankerResult` avec `final_pick_index` + `confidence`.
  7. Composite score : max(python_score, python_score * 0.6 + ai_conf * 40)
     — l'IA peut booster jusqu'à +40 pts au-dessus du python-only si elle
     confirme fort ; si l'IA vote autre, le winner reste le python-top.
  8. Winner : le candidat au meilleur final_score.
  9. History : event `searched` avec breakdown COMPLET par candidat
     (python/rules/AI/final) + winner + pipeline stages. UI Phase 2 lira
     ça pour afficher un panneau détaillé façon "AI enrichment run".

L'entrée principale `run_wanted_search()` est utilisable :
  - Manuel (UI clique "Recherche") — `trigger="manual"`
  - Auto à la création d'une issue wanted — `trigger="auto_on_create"`
  - Scheduler périodique (Phase 2) — `trigger="scheduled"`

Retour typé pour permettre à l'appelant (search endpoint OU auto-grabber)
de décider quoi faire. Le service NE fait PAS d'auto-grab lui-même en
Phase 1 — c'est le caller (endpoint, hook creation, scheduler) qui
déclenche `download_service.grab_release` sur le winner si
`winner_confidence >= config.wanted_search_auto_grab_threshold`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.issue import Issue
from app.models.magazine import Magazine
from app.parser.magazine_parser import parse_magazine_filename

logger = logging.getLogger(__name__)


# ─── Dataclasses ──────────────────────────────────────────────────────


@dataclass
class ScoredCandidate:
    """Un candidat après passage complet dans le pipeline.

    Attributs :
      - `python_score` : score du scorer Python (title fuzzy + quality +
        size + seeds + age), 0-100.
      - `rules_verdict` : "included" | "excluded" | "neutral" — appliqué
        contre les rules du magazine. "excluded" = drop de la sélection.
      - `rules_reason` : détail de la rule ayant matché (pour trace).
      - `is_blocklisted` : contrôle local vs blocklist.
      - `ai_batch_index` / `ai_verdict` / `ai_confidence` : trace IA
        quand elle est passée. `ai_verdict` = "picked" | "not_picked" |
        "vetoed" | "skipped" (skipped = IA désactivée / ≤ 1 candidat).
      - `final_score` : composite Python + IA, 0-100. Base du tri final.
      - `is_winner` : true pour le winner unique du run (ou aucun).
      - `dropped_reason` : renseigné si le candidat a été retiré de la
        sélection (excluded / blocklisted). None sinon.
    """

    guid: str
    title: str
    indexer: str
    source: str
    size: int
    age: int
    protocol: str
    seeders: int | None
    quality: str
    language: str
    download_url: str
    publish_date: str | None

    parsed_number: int | None = None
    parsed_year: int | None = None
    parsed_month: int | None = None
    parsed_day: int | None = None

    python_score: float = 0.0

    rules_verdict: str = "neutral"
    rules_reason: str | None = None
    is_blocklisted: bool = False

    ai_verdict: str = "skipped"
    ai_confidence: float | None = None
    ai_reason: str | None = None
    ai_batch_index: int | None = None

    final_score: float = 0.0
    is_winner: bool = False
    dropped_reason: str | None = None
    # Liste des queries (templates rendus) qui ont fait remonter ce
    # release. Un release remonté sur "titre 20 août 2026" ET
    # "titre 20/08/2026" a les deux — trace pour diagnostiquer quelle
    # formule marche pour ce magazine.
    matched_queries: list[str] = field(default_factory=list)


@dataclass
class WantedSearchResult:
    """Résultat structuré d'un run de recherche wanted."""

    magazine_id: int
    magazine_title: str
    issue_id: int
    issue_label: str
    query: str  # Legacy — 1re query rendue (pour compat rendu ancien)
    trigger: str  # 'manual' | 'auto_on_create' | 'scheduled'

    started_at: str
    finished_at: str
    elapsed_ms: int

    indexers_queried: list[str]
    indexer_errors: list[dict[str, Any]] = field(default_factory=list)

    total_raw: int = 0
    total_after_rules: int = 0
    total_after_blocklist: int = 0
    total_after_date_match: int = 0
    ai_used: bool = False
    ai_run_id: int | None = None
    ai_mode: str | None = None

    winner_guid: str | None = None
    winner_title: str | None = None
    winner_confidence: float | None = None
    auto_grab_threshold: float = 78.0
    auto_grab_eligible: bool = False
    auto_grab_attempted: bool = False
    auto_grab_success: bool | None = None
    auto_grab_message: str | None = None
    # Liste des queries envoyées à Prowlarr (templates rendus).
    queries_used: list[str] = field(default_factory=list)

    candidates: list[ScoredCandidate] = field(default_factory=list)


# ─── Pipeline ─────────────────────────────────────────────────────────


_MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
_MONTHS_EN = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def _build_query_context(magazine: Magazine, issue: Issue) -> dict[str, Any]:
    """Contexte de rendu des templates. Chaque clé None empêche le
    rendu d'un template qui la référence (skip propre)."""
    title = (magazine.search_terms or magazine.title or "").strip()
    number = issue.number
    year = issue.year
    month = issue.month
    day = issue.day
    return {
        "title": title,
        "number": number,
        "year": year,
        "month": month,
        "day": day,
        "month_pad": f"{month:02d}" if month else None,
        "day_pad": f"{day:02d}" if day else None,
        "month_fr": _MONTHS_FR[month - 1] if month and 1 <= month <= 12 else None,
        "month_en": _MONTHS_EN[month - 1] if month and 1 <= month <= 12 else None,
    }


def _render_template(template: str, ctx: dict[str, Any]) -> str | None:
    """Rend un template avec strict-check des placeholders.

    Retourne None si un placeholder référencé a une valeur None dans ctx
    (ex: `{number}` sur une issue sans numéro). Le rendu utilise
    ``str.format`` standard donc supporte les format specs Python
    (``{month:02d}``, etc.) — mais les templates par défaut passent
    plutôt par les alias ``month_pad``/``day_pad`` pour lisibilité YAML.
    """
    import re
    # Extract placeholders name (avant `:` s'il y a un format spec)
    placeholders = re.findall(r"\{(\w+)(?::[^}]+)?\}", template)
    for ph in placeholders:
        if ph not in ctx or ctx.get(ph) is None:
            return None
    try:
        rendered = template.format(**ctx).strip()
        # Écrase les espaces multiples résultant d'un `{}` vide
        rendered = re.sub(r"\s+", " ", rendered)
        return rendered or None
    except (KeyError, ValueError, IndexError):
        return None


def _build_queries(
    magazine: Magazine, issue: Issue, templates: list[str],
) -> list[str]:
    """Rend tous les templates fournis + dedupe case-insensitive.

    Toujours au moins UNE query : si tous les templates sont skippés
    (issue sans numéro NI date), retourne juste le titre magazine —
    évite un empty search silencieux qui laisserait l'issue jamais
    scannée.
    """
    ctx = _build_query_context(magazine, issue)
    seen: set[str] = set()
    out: list[str] = []
    for tpl in templates:
        rendered = _render_template(tpl, ctx)
        if rendered is None:
            continue
        key = rendered.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(rendered)
    if not out:
        # Fallback = titre magazine seul (dernier recours)
        out.append(ctx["title"])
    return out


def _build_query(magazine: Magazine, issue: Issue) -> str:
    """Legacy shim — retourne la première query dérivée du contexte.
    Utilisé par les callers qui n'ont pas encore migré vers multi-query."""
    return _build_queries(magazine, issue, [
        "{title} N{number}",
        "{title} {year} {month_pad} {day_pad}",
        "{title} {year} {month_pad}",
    ])[0]


def _issue_label(issue: Issue) -> str:
    """Étiquette lisible d'une issue pour logs/UI."""
    parts: list[str] = []
    if issue.number is not None:
        parts.append(f"#{issue.number}")
    if issue.year:
        date = f"{issue.year}"
        if issue.month:
            date = f"{issue.month:02d}/{date}"
        if issue.day:
            date = f"{issue.day:02d}/{date}"
        parts.append(date)
    return " ".join(parts) or f"id{issue.id}"


async def _fetch_from_prowlarr(
    db: AsyncSession,
    queries: list[str],
) -> tuple[list, list[str], list[dict]]:
    """Query all enabled Prowlarr indexers pour CHAQUE query fournie et
    dédup les résultats par GUID (un release qui remonte sur 3 formats
    de date n'est compté qu'une fois).

    Retourne (raw_results, indexer_names, errors). Chaque raw est taggé
    avec `_pressarr_indexer` (nom indexer) + `_pressarr_matched_queries`
    (list des queries qui l'ont fait remonter → utile pour UI diagnostic
    "cette requête n'a rien donné mais celle-ci si").
    """
    from app.indexers.prowlarr import ProwlarrClient
    from app.models.indexer_config import IndexerConfig
    from app.services.search_service import (
        get_search_groups,
        parse_indexer_overrides,
    )

    indexer_result = await db.execute(
        select(IndexerConfig).where(IndexerConfig.enabled.is_(True))
    )
    indexers = indexer_result.scalars().all()

    # GUID → raw (dedup). Un même release remonté sur plusieurs queries
    # accumule les queries dans _pressarr_matched_queries.
    by_guid: dict[str, Any] = {}
    names: list[str] = []
    errors: list[dict] = []
    for indexer in indexers:
        names.append(indexer.name)
        try:
            client = ProwlarrClient(url=indexer.url, api_key=indexer.api_key)
            global_cats = [
                int(c) for c in indexer.categories.split(",") if c.strip().isdigit()
            ] or [7000, 7010, 7020]
            overrides = parse_indexer_overrides(indexer.indexer_overrides)
            search_groups = get_search_groups(overrides, global_cats)
            for query in queries:
                for cats, indexer_ids in search_groups:
                    res = await client.search(
                        query, categories=cats, indexer_ids=indexer_ids
                    )
                    for r in res:
                        gid = getattr(r, "guid", None) or f"{indexer.name}:{r.title}"
                        existing = by_guid.get(gid)
                        if existing is None:
                            setattr(r, "_pressarr_indexer", indexer.name)
                            setattr(r, "_pressarr_matched_queries", [query])
                            by_guid[gid] = r
                        else:
                            # Ajoute la query au tracker sans dupliquer
                            mq = getattr(existing, "_pressarr_matched_queries", [])
                            if query not in mq:
                                mq.append(query)
                                setattr(existing, "_pressarr_matched_queries", mq)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Prowlarr fetch failed for %s: %s", indexer.name, err,
                exc_info=True,
            )
            errors.append({"indexer": indexer.name, "error": err[:400]})
    return list(by_guid.values()), names, errors


async def _apply_ai_ranker(
    candidates: list[ScoredCandidate],
    magazine: Magazine,
    issue: Issue,
    config,
    session_factory,
) -> tuple[str | None, int | None, dict[int, dict]]:
    """Passe les candidats non-droppés dans le ranker IA batch+arbiter.

    Retourne (applied_mode, run_id, per_candidate_ai_data). La map
    per_candidate_ai_data est indexée sur la position du candidat dans
    la liste FILTRÉE (post-rules/blocklist) qu'on envoie au ranker.
    Chaque entrée : {verdict, confidence, reason, batch_index}.
    """
    from app.services.ai_ranker_service import (
        AIRankerService,
        RankerCandidate,
    )

    ranker_candidates = [
        RankerCandidate(
            id=c.guid,
            title=c.title,
            publish_date=c.publish_date,
        )
        for c in candidates
    ]
    svc = AIRankerService(config, session_factory)
    result = await svc.rank(
        candidates=ranker_candidates,
        magazine_id=magazine.id,
        pattern_id=None,
        magazine_title_hint=magazine.title,
        issue_hint=_issue_label(issue),
        issue_id=issue.id,
    )

    per_candidate: dict[int, dict] = {}
    picked = result.final_pick_index
    scorer_top = result.scorer_top_index
    confidence = result.confidence
    reason = result.reason

    for idx, cand in enumerate(candidates):
        verdict = "not_picked"
        if idx == picked:
            verdict = "picked"
        elif idx == scorer_top and result.vetoed_top:
            verdict = "vetoed"
        per_candidate[idx] = {
            "verdict": verdict,
            "confidence": (confidence if idx == picked else None),
            "reason": (reason if idx == picked else None),
            "batch_index": None,  # ai_ranker n'expose pas la batch/candidat
        }

    return result.applied_mode, result.run_id, per_candidate


def _candidate_matches_issue(
    cand: "ScoredCandidate",
    issue: Issue,
    date_tolerance_days: int = 0,
) -> bool:
    """Vérifie qu'un candidat correspond à l'issue cible (date OU numéro).

    Règles strictes :
      - Si l'issue a un numéro connu ET le candidat aussi → match par
        numéro strict (numéros de publication uniques).
      - Sinon match par date :
        * si l'issue a un jour précis (typique daily/weekly), on
          exige que le candidat AIT AUSSI un jour parsé et qu'il
          matche. Un candidat avec year+month mais day=None est
          REJETÉ.
        * si l'issue n'a pas de jour (monthly+), year+month suffisent.
      - Un candidat avec ZÉRO info parsée (title mal formé) garde le
        bénéfice du doute → le ranker IA tranchera.

    ``date_tolerance_days`` : tolérance en jours autour de issue.day.
    Utile pour magazines à édition combinée weekend (ex: Le Monde
    "15,16,17 août" = 1 issue publiée le 17, avec tolerance=2 les
    releases datés 15,16,17 matchent tous cette issue).
    """
    # Match par numéro d'abord (plus fiable)
    if issue.number is not None and cand.parsed_number is not None:
        return cand.parsed_number == issue.number

    # Match par date
    if issue.year and cand.parsed_year is not None:
        if cand.parsed_year != issue.year:
            return False
        if issue.month:
            if cand.parsed_month is None:
                return False
            if cand.parsed_month != issue.month:
                return False
            if issue.day:
                if cand.parsed_day is None:
                    return False
                # Tolérance jour magazine-driven pour éditions combinées.
                tol = max(0, int(date_tolerance_days))
                if abs(cand.parsed_day - issue.day) > tol:
                    return False
        return True

    # Aucune info parsée → bénéfice du doute
    if (
        cand.parsed_year is None
        and cand.parsed_month is None
        and cand.parsed_day is None
        and cand.parsed_number is None
    ):
        return True

    # Il y a de l'info parsée mais elle ne matche pas → drop
    return False


def _composite_score(
    python_score: float,
    ai_verdict: str,
    ai_confidence: float | None,
    ai_mode: str | None,
) -> float:
    """Combine python + IA en un score 0-100, respectant le mode ranker.

    Correction post-incident (Le Monde 2928 imported "Le Figaro Magazine"
    content) : le boost IA était appliqué même en mode ``ai_advisory``,
    ce qui permettait à un pick IA erroné de propulser un candidat
    off-topic au-dessus du seuil auto-grab. Le mode advisory par défaut
    est censé LOGGER l'avis IA sans le laisser influencer le winner.

    Règles par mode :
      - ``ai_advisory`` (défaut) : IA log seul, aucune influence sur
        le composite. final_score = python_score.
      - ``ai_veto_only`` : l'IA peut REFUSER le top scorer (down-score
        à /3) mais ne peut pas booster un autre candidat au-dessus.
      - ``ai_wins`` : IA autorité pleine. Pick IA boosté par
        max(python, python*0.6 + conf*40). Veto down-score /3.
    """
    if ai_mode == "ai_wins":
        if ai_verdict == "picked" and ai_confidence is not None:
            return max(python_score, python_score * 0.6 + ai_confidence * 40.0)
        if ai_verdict == "vetoed":
            return python_score / 3.0
        return python_score
    if ai_mode == "ai_veto_only":
        if ai_verdict == "vetoed":
            return python_score / 3.0
        return python_score
    # ai_advisory (défaut) et tout mode inconnu → passthrough python
    return python_score


async def run_wanted_search(
    db: AsyncSession,
    issue_id: int,
    config,
    trigger: str = "manual",
    session_factory=None,
    enable_auto_grab: bool = True,
) -> WantedSearchResult:
    """Point d'entrée du pipeline.

    Si ``enable_auto_grab`` (défaut True) ET le winner passe le seuil
    ``wanted_search_auto_grab_threshold``, déclenche le grab automatique
    via `download_service.grab_release`. Le résultat structuré indique
    dans tous les cas si l'auto-grab a été tenté (`auto_grab_attempted`)
    et son issue (`auto_grab_result`). Passer False pour un run manuel
    "aperçu" qui ne doit jamais toucher le download client.

    Toggles :
      - ``config.wanted_search_enabled`` : global. False = tous les
        triggers automatiques (auto_on_create, scheduled) skippent.
        ``trigger="manual"`` outrepasse le toggle global (l'user
        garde toujours la main via le bouton UI).
      - ``magazine.wanted_search_enabled`` : per-mag. False = skip
        même en manuel (l'utilisateur a explicitement gelé ce mag).
    """
    from app.services import activity_service
    from app.services.history_service import create_event, is_blocklisted
    from app.services.magazine_service import apply_magazine_rules
    from app.services.search_service import (
        _get_quality_items,
        score_release,
    )

    t0 = time.monotonic()

    # 1. Load issue + magazine + rules
    row = await db.execute(
        select(Issue)
        .options(
            selectinload(Issue.magazine).selectinload(Magazine.rules),
        )
        .where(Issue.id == issue_id)
    )
    issue = row.scalars().first()
    if issue is None:
        raise ValueError(f"issue {issue_id} not found")
    magazine = issue.magazine
    if magazine is None:
        raise ValueError(f"issue {issue_id} has no magazine")

    templates = getattr(config, "wanted_search_query_templates", None) or [
        "{title} N{number}",
        "{title} {year} {month_pad} {day_pad}",
    ]
    queries = _build_queries(magazine, issue, templates)
    # Field `query` du result reste single-line pour compat/history ancien
    # affichage — on prend la première (celle qui match le plus de
    # placeholders). La liste complète est exposée via `queries_used`.
    query = queries[0] if queries else magazine.title
    started_at = datetime.now().isoformat(timespec="seconds")

    # Toggles — skip early avec un résultat vide "propre" pour que le
    # caller distingue "désactivé" (0 candidats + trigger=disabled) vs
    # "recherché sans résultat".
    global_off = trigger != "manual" and not getattr(
        config, "wanted_search_enabled", True,
    )
    mag_off = not getattr(magazine, "wanted_search_enabled", True)
    if global_off or mag_off:
        finished_at = datetime.now().isoformat(timespec="seconds")
        reason = "global_disabled" if global_off else "magazine_disabled"
        logger.info(
            "wanted_search skipped for issue %s (%s, trigger=%s)",
            issue_id, reason, trigger,
        )
        return WantedSearchResult(
            magazine_id=magazine.id,
            magazine_title=magazine.title,
            issue_id=issue.id,
            issue_label=_issue_label(issue),
            query=query,
            trigger=f"{trigger}:{reason}",
            started_at=started_at,
            finished_at=finished_at,
            elapsed_ms=0,
            indexers_queried=[],
            queries_used=queries,
        )

    # Activity live pour l'UI (progress + steps).
    activity_id: int | None = None
    try:
        activity_id = await activity_service.create(
            kind="search",
            title=f"Recherche · {magazine.title} {_issue_label(issue)}",
            subtitle=f"{len(queries)} query(s) · " + query,
            magazine_id=magazine.id,
            issue_id=issue.id,
            payload={"query": query, "queries": queries, "trigger": trigger},
        )
    except Exception:
        logger.debug("activity mirror create failed", exc_info=True)

    async def _step(step: str, label: str, hint: str | None = None) -> None:
        if activity_id is None:
            return
        try:
            await activity_service.push_step(
                activity_id,
                {"step": step, "label": label, "hint": hint},
            )
        except Exception:
            pass

    # 2. Fetch — envoie les N queries à tous les indexers, résultats
    # dédupés par GUID. Chaque candidat garde la trace des queries qui
    # l'ont fait remonter (utile pour diagnostiquer "quelle formule
    # marche pour ce magazine").
    await _step(
        "fetch", "Prowlarr",
        f"{len(queries)} query(s) · " + " · ".join(queries[:3])
        + (f" · +{len(queries)-3}" if len(queries) > 3 else ""),
    )
    raw_results, indexer_names, indexer_errors = await _fetch_from_prowlarr(
        db, queries,
    )

    profile_items = await _get_quality_items(db, magazine.quality_profile_id)

    # 3. Parse + Python score + rules + blocklist
    await _step("score", "Scoring", f"{len(raw_results)} résultats bruts")
    from app.services.search_service import _resolve_language

    candidates: list[ScoredCandidate] = []
    for raw in raw_results:
        parsed = parse_magazine_filename(raw.title)
        quality = parsed.quality if parsed.quality != "unknown" else "unknown"
        language = _resolve_language(raw.language, parsed.language)
        py_score = score_release(
            title=raw.title,
            quality=quality,
            size=raw.size,
            seeders=raw.seeders,
            age_days=raw.age,
            magazine_title=magazine.title,
            profile_items=profile_items,
        )
        rules_probe = f"{parsed.title or ''} {raw.title}".strip()
        excluded, reason = apply_magazine_rules(
            rules_probe, list(magazine.rules or []),
        )
        blocked = await is_blocklisted(db, raw.title)

        cand = ScoredCandidate(
            matched_queries=list(getattr(raw, "_pressarr_matched_queries", [])),
            guid=raw.guid,
            title=raw.title,
            indexer=getattr(raw, "_pressarr_indexer", ""),
            source=raw.indexer,
            size=raw.size,
            age=raw.age,
            protocol=raw.protocol,
            seeders=raw.seeders,
            quality=quality,
            language=language,
            download_url=raw.download_url or "",
            publish_date=raw.publish_date,
            parsed_number=parsed.number,
            parsed_year=parsed.year,
            parsed_month=parsed.month,
            parsed_day=parsed.day,
            python_score=py_score,
            rules_verdict="excluded" if excluded else "neutral",
            rules_reason=reason,
            is_blocklisted=blocked,
        )
        if excluded:
            cand.dropped_reason = f"rule: {reason}"
        elif blocked:
            cand.dropped_reason = "blocklisted"
        candidates.append(cand)

    total_raw = len(candidates)
    surviving = [c for c in candidates if c.dropped_reason is None]
    surviving.sort(key=lambda c: c.python_score, reverse=True)
    total_after_rules = sum(1 for c in candidates if c.rules_verdict != "excluded")
    total_after_blocklist = len(surviving)

    # 3bis. Filtre date/numéro match issue — Prowlarr renvoie souvent TOUS
    # les releases d'un magazine sur n'importe quelle query. Sans ce
    # filtre le ranker IA voyait 15 candidats de dates différentes pour
    # une issue précise → picks incohérents (ex: "Le Monde 19/08" pour
    # issue 20/08). On drop les candidats dont la date parsée contredit
    # l'issue cible avec drop_reason lisible côté UI.
    date_matched: list[ScoredCandidate] = []
    mag_tol = int(getattr(magazine, "date_tolerance_days", 0) or 0)
    for c in surviving:
        if _candidate_matches_issue(c, issue, date_tolerance_days=mag_tol):
            date_matched.append(c)
        else:
            # Marque comme droppé pour trace UI (visible dans table "Rejetés")
            bits = []
            if c.parsed_number is not None:
                bits.append(f"N°{c.parsed_number}")
            if c.parsed_year and c.parsed_month:
                d = f"{c.parsed_year}-{c.parsed_month:02d}"
                if c.parsed_day:
                    d += f"-{c.parsed_day:02d}"
                bits.append(d)
            detail = " ".join(bits) or "aucune date parsée"
            c.dropped_reason = f"date mismatch ({detail} ≠ cible {_issue_label(issue)})"
    total_after_date_match = len(date_matched)
    # Utilise les date-matched pour la suite ; si vide, on garde
    # surviving (fallback : mieux vaut ranker mal que rien du tout,
    # l'user verra le résultat et pourra grabber manuellement).
    ranker_pool = date_matched if date_matched else surviving
    ranker_pool.sort(key=lambda c: c.python_score, reverse=True)

    # 4. IA batch + arbiter (top-K)
    ai_run_id: int | None = None
    ai_mode: str | None = None
    ai_used = False
    if getattr(config, "ai_ranker_enabled", False) and len(ranker_pool) >= 2:
        top_k = min(getattr(config, "ai_ranker_top_k", 15), len(ranker_pool))
        subset = ranker_pool[:top_k]
        await _step("ai", "IA ranker", f"batch {len(subset)} candidats")
        try:
            ai_mode, ai_run_id, ai_map = await _apply_ai_ranker(
                subset, magazine, issue, config,
                session_factory or None,
            )
            ai_used = True
            for idx, cand in enumerate(subset):
                info = ai_map.get(idx, {})
                cand.ai_verdict = info.get("verdict", "not_picked")
                cand.ai_confidence = info.get("confidence")
                cand.ai_reason = info.get("reason")
                cand.ai_batch_index = info.get("batch_index")
        except Exception:
            logger.warning(
                "IA ranker failed for issue %s — fallback python-only",
                issue_id, exc_info=True,
            )

    # 5. Composite score + winner (calculé sur ranker_pool = date-matched)
    ai_mode_actual = ai_mode or (
        getattr(config, "ai_ranker_mode", "ai_advisory") if ai_used else None
    )
    for c in ranker_pool:
        c.final_score = _composite_score(
            c.python_score, c.ai_verdict, c.ai_confidence, ai_mode_actual,
        )
    ranker_pool.sort(key=lambda c: c.final_score, reverse=True)
    winner = ranker_pool[0] if ranker_pool else None
    if winner is not None:
        winner.is_winner = True

    finished_at = datetime.now().isoformat(timespec="seconds")
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    result = WantedSearchResult(
        magazine_id=magazine.id,
        magazine_title=magazine.title,
        issue_id=issue.id,
        issue_label=_issue_label(issue),
        query=query,
        queries_used=queries,
        trigger=trigger,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_ms=elapsed_ms,
        indexers_queried=indexer_names,
        indexer_errors=indexer_errors,
        total_raw=total_raw,
        total_after_rules=total_after_rules,
        total_after_blocklist=total_after_blocklist,
        total_after_date_match=total_after_date_match,
        ai_used=ai_used,
        ai_run_id=ai_run_id,
        ai_mode=ai_mode,
        winner_guid=winner.guid if winner else None,
        winner_title=winner.title if winner else None,
        winner_confidence=winner.final_score if winner else None,
        auto_grab_threshold=float(
            getattr(config, "wanted_search_auto_grab_threshold", 78.0),
        ),
        auto_grab_eligible=(
            winner is not None
            and winner.final_score
            >= float(getattr(config, "wanted_search_auto_grab_threshold", 78.0))
        ),
        candidates=candidates,
    )

    # Marque l'issue comme scannée pour que le scheduler respecte le
    # cooldown. Best-effort — un échec ici n'empêche pas le return.
    try:
        issue.last_searched_at = datetime.now()
        await db.flush()
    except Exception:
        logger.debug("last_searched_at update failed", exc_info=True)

    # 6bis. Auto-grab automatique si eligible (winner >= threshold)
    #
    # Garde-fous cumulés post-incident :
    #   1. `enable_auto_grab` caller-side (respect du contexte : preview
    #      manuel = False).
    #   2. `config.wanted_search_auto_grab_enabled` global — défaut False
    #      après l'écrasement d'un fichier Le Monde par un release Le
    #      Figaro Magazine, force l'user à opt-in explicitement.
    #   3. Winner confidence >= threshold (défaut 78%).
    #   4. Fuzzy match du titre magazine >= min_title_match (défaut 60%)
    #      sur le TITRE DU RELEASE — garde-fou indépendant du composite
    #      score, bloque les picks IA off-topic même à confidence 1.0.
    global_auto_grab = getattr(config, "wanted_search_auto_grab_enabled", False)
    auto_grab_gate_ok = (
        enable_auto_grab
        and global_auto_grab
        and winner is not None
        and result.auto_grab_eligible
        and winner.download_url is not None
        and winner.download_url != ""
    )
    if auto_grab_gate_ok and winner is not None:
        # Hard gate fuzzy titre — le release doit ressembler au titre
        # magazine à un plancher minimum. Empêche IA d'auto-grab un
        # "Le Figaro Magazine" quand la cible est "Le Monde".
        min_title = float(
            getattr(config, "wanted_search_min_title_match", 60.0),
        )
        title_gate_score: float | None = None
        try:
            from app.parser.magazine_parser import fuzzy_match_title as _fuzzy
            _m = _fuzzy(winner.title, [magazine.title], threshold=0.0)
            if _m:
                _, title_gate_score = _m
        except Exception:
            logger.debug("fuzzy title gate check failed", exc_info=True)

        if title_gate_score is None or title_gate_score < min_title:
            logger.warning(
                "auto-grab bloqué pour issue %s : fuzzy titre %s vs %r = %s < %.1f",
                issue_id, winner.title[:60], magazine.title,
                f"{title_gate_score:.1f}" if title_gate_score is not None else "?",
                min_title,
            )
            result.auto_grab_attempted = False
            result.auto_grab_success = False
            result.auto_grab_message = (
                f"blocked: title match {title_gate_score:.0f}% < {min_title:.0f}%"
                if title_gate_score is not None else "blocked: title gate error"
            )
            auto_grab_gate_ok = False

    if auto_grab_gate_ok and winner is not None:
        # Hard gate score Python : même si l'IA boostait le composite
        # au-dessus du seuil, un python_score bas signale que le
        # release ne correspond pas objectivement (mauvais titre, pas
        # de seed, quality inconnue). L'IA seule ne doit pas pouvoir
        # trancher — les deux (python ET IA) doivent être positifs.
        min_py = float(
            getattr(config, "wanted_search_min_python_score", 55.0),
        )
        if winner.python_score < min_py:
            logger.warning(
                "auto-grab bloqué pour issue %s : python_score %.1f < %.1f "
                "(l'IA seule ne peut pas décider si Python est KO)",
                issue_id, winner.python_score, min_py,
            )
            result.auto_grab_attempted = False
            result.auto_grab_success = False
            result.auto_grab_message = (
                f"blocked: python_score {winner.python_score:.0f} < {min_py:.0f} "
                f"(IA seule insuffisante)"
            )
            auto_grab_gate_ok = False

    if auto_grab_gate_ok and winner is not None:
        # Vérifie l'issue est toujours wanted — évite un race avec un
        # grab manuel qui aurait passé l'issue en snatched entre-temps.
        await db.refresh(issue)
        if issue.status == "wanted" and issue.monitored:
            await _step(
                "auto_grab",
                "Auto-grab",
                f"{winner.final_score:.0f}% ≥ {result.auto_grab_threshold:.0f}%",
            )
            try:
                from app.services.download_service import grab_release
                grab_resp = await grab_release(
                    db,
                    issue_id=issue.id,
                    download_url=winner.download_url,
                    title=winner.title,
                    protocol=winner.protocol,
                    guid=winner.guid,
                    match_score=winner.final_score,
                    match_details=(
                        f"wanted_search auto ({trigger}) — "
                        f"python {winner.python_score:.1f} · "
                        f"IA {winner.ai_verdict}"
                        + (
                            f" ({winner.ai_confidence:.2f})"
                            if winner.ai_confidence is not None
                            else ""
                        )
                    ),
                )
                result.auto_grab_attempted = True
                result.auto_grab_success = bool(grab_resp.download_id)
                result.auto_grab_message = grab_resp.message
                logger.info(
                    "wanted_search auto-grab issue %s → %s (%s)",
                    issue_id, grab_resp.message,
                    "ok" if grab_resp.download_id else "no_dl_id",
                )
            except Exception as exc:
                result.auto_grab_attempted = True
                result.auto_grab_success = False
                result.auto_grab_message = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "auto-grab failed for issue %s: %s",
                    issue_id, exc, exc_info=True,
                )
        else:
            logger.debug(
                "auto-grab skipped for issue %s: status=%s monitored=%s",
                issue_id, issue.status, issue.monitored,
            )

    # 6. History event (payload lisible pour UI Phase 2)
    try:
        # Cap : 25 candidats persistés max (les autres sont dans le
        # ScoredCandidate returned mais pas en DB — history event pas fait
        # pour stocker 500 rows).
        cand_slice = candidates[:25]
        await create_event(
            db,
            event_type="searched",
            magazine_id=magazine.id,
            issue_id=issue.id,
            details=(
                f"Wanted search: {query} · {total_raw} bruts · "
                f"{total_after_blocklist} candidats · "
                + (
                    f"winner={winner.title[:80]} ({winner.final_score:.1f}%)"
                    if winner else "aucun winner"
                )
            ),
            data={
                "search_type": trigger,
                "query": query,
                "queries": queries,
                "magazine_title": magazine.title,
                "issue_label": _issue_label(issue),
                "elapsed_ms": elapsed_ms,
                "indexers": indexer_names,
                "indexer_errors": indexer_errors,
                "totals": {
                    "raw": total_raw,
                    "after_rules": total_after_rules,
                    "after_blocklist": total_after_blocklist,
                    "after_date_match": total_after_date_match,
                    "candidates_persisted": len(cand_slice),
                },
                "ai": {
                    "used": ai_used,
                    "mode": ai_mode,
                    "run_id": ai_run_id,
                },
                "winner": (
                    {
                        "guid": winner.guid,
                        "title": winner.title,
                        "confidence": round(winner.final_score, 1),
                        "python_score": round(winner.python_score, 1),
                        "ai_verdict": winner.ai_verdict,
                        "ai_confidence": winner.ai_confidence,
                        "indexer": winner.indexer,
                        "quality": winner.quality,
                        "auto_grab_eligible": result.auto_grab_eligible,
                    }
                    if winner else None
                ),
                "auto_grab": {
                    "threshold": result.auto_grab_threshold,
                    "eligible": result.auto_grab_eligible,
                    "attempted": result.auto_grab_attempted,
                    "success": result.auto_grab_success,
                    "message": result.auto_grab_message,
                },
                "candidates": [
                    {
                        "guid": c.guid,
                        "title": c.title[:200],
                        "indexer": c.indexer,
                        "quality": c.quality,
                        "size": c.size,
                        "seeders": c.seeders,
                        "python_score": round(c.python_score, 1),
                        "rules_verdict": c.rules_verdict,
                        "rules_reason": c.rules_reason,
                        "is_blocklisted": c.is_blocklisted,
                        "ai_verdict": c.ai_verdict,
                        "ai_confidence": c.ai_confidence,
                        "ai_reason": c.ai_reason,
                        "final_score": round(c.final_score, 1),
                        "is_winner": c.is_winner,
                        "dropped_reason": c.dropped_reason,
                        "matched_queries": c.matched_queries,
                    }
                    for c in cand_slice
                ],
            },
        )
        # Commit explicite du searched event + tout autre write
        # pending (last_searched_at, matched_magazine liens éventuels).
        # Sans ce commit, le context manager du caller (scheduler,
        # endpoint) sortait sans commit → tous les writes du run
        # étaient rollback silencieusement, d'où 0 event `searched`
        # en DB malgré des dizaines de runs enregistrés par le
        # scheduler comme "complete".
        await db.commit()
    except Exception:
        logger.warning(
            "Failed to persist searched event for issue %s (non-fatal)",
            issue_id, exc_info=True,
        )
        try:
            await db.rollback()
        except Exception:
            pass

    if activity_id is not None:
        try:
            hint = (
                f"winner {winner.final_score:.0f}% · {winner.title[:60]}"
                if winner else "aucun candidat"
            )
            await activity_service.mark_done(activity_id, hint=hint)
        except Exception:
            pass

    return result


def trigger_wanted_search_in_background(issue_id: int) -> None:
    """Fire-and-forget : lance un run wanted_search en background sans
    bloquer le caller (issue creation, promote_forecast, etc.).

    Ne lève JAMAIS — les erreurs sont logguées et l'issue reste wanted
    pour être picked par le scheduler suivant (Phase 2). Un run raté ici
    ne doit pas casser la création d'issue qui l'a déclenché.
    """
    from app.database import async_session_factory
    from app.dependencies import get_config

    if async_session_factory is None:
        return

    async def _bg():
        try:
            async with async_session_factory() as db:
                await run_wanted_search(
                    db, issue_id, get_config(),
                    trigger="auto_on_create",
                    session_factory=async_session_factory,
                )
        except Exception:
            logger.exception(
                "Background wanted_search failed for issue %s (non-fatal)",
                issue_id,
            )

    try:
        asyncio.get_running_loop().create_task(_bg())
    except RuntimeError:
        # Pas de loop running (appel depuis un context sync bizarre) — ignore
        logger.debug(
            "No running event loop — skipping background search for issue %s",
            issue_id,
        )
