"""Metadata pipeline registry — modular hook points.

Objectif : donner à un futur développeur (ou à l'utilisateur qui
veut ajouter un nouveau moteur) un endroit unique où déclarer une
étape sans avoir à toucher le code du pipeline monolithique
``AIEnrichmentService.enrich()``.

**État actuel (Phase 3)** : le pipeline reste procédural dans
``ai_enrichment_service.enrich()``. Ce registre décrit l'ordre
d'exécution des steps, leur rôle et leurs contrats I/O pour
l'auto-documentation (Settings/AI page + History drill-down).

**Utilisation future** : à terme, ``enrich()`` itèrera
sur ``list_steps()`` et déléguera à chaque ``PipelineStep``
concret. Pour l'instant on garde le pipeline en dur et on utilise
ce registre uniquement comme *source de vérité affichable*.

Ajouter une nouvelle étape :
  1. Créer une classe ou une fonction async(ctx) -> step_dict
  2. L'enregistrer via ``@register_step(name, ...)``
  3. L'insérer à la bonne position via ``insert_before/after``
     (une prochaine itération câblera l'exécution automatique).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepDescriptor:
    """Décrit une étape du pipeline metadata pour la doc + UI."""

    name: str                       # identifiant machine (ex. "vision")
    label: str                      # nom affiché en français
    description: str                # 1-2 lignes pour l'UI
    kind: str                       # "deterministic" | "llm" | "ocr" | "system"
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    optional: bool = False          # sautable via config
    fan_out: bool = False           # produit N steps (une par zone)


# Registre en ordre d'exécution. Chaque nouvelle étape s'ajoute ici.
_STEPS: list[StepDescriptor] = [
    StepDescriptor(
        name="text",
        label="Analyse IA du nom torrent",
        description=(
            "Extrait titre, N°, année, mois, jour depuis le nom de "
            "fichier avec le modèle texte (mistral:7b par défaut). "
            "Source de vérité primaire — jamais écrasée."
        ),
        kind="llm",
        inputs=["torrent_name"],
        outputs=["title", "issue_number", "year", "month", "day", "is_hs"],
    ),
    StepDescriptor(
        name="switch_vision",
        label="Chargement modèle vision",
        description="Décharge le modèle texte, charge le modèle vision.",
        kind="system",
    ),
    StepDescriptor(
        name="python_ocr",
        label="OCR algorithmique",
        description=(
            "Deterministic OCR sur chaque zone (Tesseract/EasyOCR/"
            "RapidOCR). Ne peut pas halluciner — corrobore ou "
            "contredit le vision LLM."
        ),
        kind="ocr",
        inputs=["png_bytes"],
        outputs=["raw_text"],
        optional=True,
        fan_out=True,
    ),
    StepDescriptor(
        name="vision",
        label="OCR IA vision",
        description=(
            "OCR par IA vision sur chaque zone avec prompt adapté au "
            "tag (number/date/title/…). Un appel par zone."
        ),
        kind="llm",
        inputs=["png_bytes", "tag", "custom_tag", "vision_prompt"],
        outputs=["title", "raw_text"],
        optional=True,
        fan_out=True,
    ),
    StepDescriptor(
        name="switch_text",
        label="Rechargement modèle arbitre",
        description="Décharge le vision, recharge le modèle arbitre.",
        kind="system",
    ),
    StepDescriptor(
        name="arbiter",
        label="Arbitrage IA (gros modèle)",
        description=(
            "Voit torrent + vision × N zones + python_ocr × N zones + "
            "candidats regex. Choisit la valeur la plus réaliste par "
            "champ. Modèle configurable (qwen3:8b recommandé)."
        ),
        kind="llm",
        inputs=["torrent", "vision_outputs", "pyocr_outputs", "python_candidates"],
        outputs=["title", "issue_number", "year", "month", "day", "issn", "confidence"],
    ),
    StepDescriptor(
        name="arbiter_postvalidate",
        label="Post-validation deterministic",
        description=(
            "Garantit que le torrent reste primaire (jamais écrasé) et "
            "restaure les valeurs Python que le LLM a « oubliées ». "
            "Détecte les hallucinations issue_number."
        ),
        kind="deterministic",
        inputs=["llm_out", "torrent", "python_candidates"],
        outputs=["title", "issue_number", "year", "month", "day"],
    ),
]


def list_steps() -> list[StepDescriptor]:
    """Ordre canonique du pipeline."""
    return list(_STEPS)


def describe_step(name: str) -> StepDescriptor | None:
    for s in _STEPS:
        if s.name == name:
            return s
    return None


def register_step(
    step: StepDescriptor,
    *,
    after: str | None = None,
    before: str | None = None,
) -> None:
    """Insère une étape dans le registre.

    Pour l'instant : documentaire (le pipeline procédural doit être
    modifié en parallèle). Une prochaine itération câblera
    l'exécution automatique via une classe base ``PipelineStep``.
    """
    idx = len(_STEPS)
    if after:
        for i, s in enumerate(_STEPS):
            if s.name == after:
                idx = i + 1
                break
    elif before:
        for i, s in enumerate(_STEPS):
            if s.name == before:
                idx = i
                break
    _STEPS.insert(idx, step)


def as_dicts() -> list[dict[str, Any]]:
    """Serialize pour l'API — sert la doc au frontend."""
    return [
        {
            "name": s.name,
            "label": s.label,
            "description": s.description,
            "kind": s.kind,
            "inputs": s.inputs,
            "outputs": s.outputs,
            "optional": s.optional,
            "fanOut": s.fan_out,
        }
        for s in _STEPS
    ]
