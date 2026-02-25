# Feature 013: Filename Parser

**Branch:** 013-filename-parser
**Date:** 2026-02-25
**Status:** Draft

## Overview

Parser robuste capable de reconnaître et décomposer les noms de fichiers magazines en leurs composants (titre, numéro, date, langue, qualité, format). Ce parser est essentiel pour l'import automatique et le matching des fichiers avec les issues connues dans la bibliothèque.

## User Stories

### US-013.1: Parser un nom de fichier standard
**En tant que** système,
**je veux** parser un nom de fichier magazine et en extraire les composants,
**afin de** identifier automatiquement le contenu du fichier.

**Critères d'acceptation :**
- [ ] Le parser extrait correctement le titre, le numéro, la date (mois + année), la langue, la qualité, et le format
- [ ] Le parser gère le format "Science.et.Vie.N1285.Mars.2025.FRENCH.PDF" et toutes les variantes courantes
- [ ] Le parser gère les numéros avec préfixe (N°, No, Issue, #, Num) et sans préfixe
- [ ] Le parser gère les volumes (Vol, Volume, V) quand présents
- [ ] Les composants non reconnus sont marqués comme "unknown" sans erreur

### US-013.2: Gérer les séparateurs multiples
**En tant que** système,
**je veux** que le parser reconnaisse les noms avec différents séparateurs,
**afin de** supporter tous les formats de nommage courants dans la scène.

**Critères d'acceptation :**
- [ ] Les séparateurs supportés sont : points (.), espaces ( ), underscores (_), tirets (-)
- [ ] Les séparateurs mixtes sont gérés (ex: "Science.et.Vie - N1285")
- [ ] Les séparateurs sont normalisés en interne pour faciliter le matching
- [ ] Les noms sans séparateur clair (ex: "ScienceEtVie1285") sont traités en best-effort

### US-013.3: Reconnaître les dates multilingues
**En tant que** système,
**je veux** que le parser reconnaisse les noms de mois dans plusieurs langues,
**afin de** supporter les magazines internationaux.

**Critères d'acceptation :**
- [ ] Les mois en français sont reconnus (Janvier, Février, Mars... et abréviations Jan, Fév, Mar...)
- [ ] Les mois en anglais sont reconnus (January, February, March... et abréviations)
- [ ] Les formats de date numériques sont reconnus (2025-03, 03-2025, 03/2025)
- [ ] Les saisons sont reconnues (Printemps/Spring, Été/Summer, Automne/Fall/Autumn, Hiver/Winter)

### US-013.4: Matcher avec les magazines connus
**En tant que** système,
**je veux** matcher le titre extrait d'un nom de fichier avec les magazines de la bibliothèque,
**afin de** rattacher automatiquement le fichier au bon magazine.

**Critères d'acceptation :**
- [ ] Le matching est fuzzy (tolérant aux différences mineures de casse, accents, ponctuation)
- [ ] "Science et Vie" matche "Science & Vie" et "Science.et.Vie"
- [ ] Un score de confiance est retourné pour chaque match (0-100%)
- [ ] Si plusieurs magazines correspondent, le meilleur match est retourné avec les alternatives
- [ ] Si aucun magazine ne correspond (score < seuil configurable), le fichier est marqué comme non reconnu

### US-013.5: Détecter les hors-séries
**En tant que** système,
**je veux** détecter les numéros hors-série dans les noms de fichiers,
**afin de** les distinguer des numéros réguliers.

**Critères d'acceptation :**
- [ ] Les marqueurs de hors-série sont reconnus : HS, Hors-Serie, Hors-Série, Special, Spécial, Bonus, Extra
- [ ] Les hors-séries sont flaggués dans le résultat du parsing
- [ ] La numérotation des hors-séries est extraite si présente (ex: "HS 12", "Special 3")
- [ ] Les hors-séries ne sont pas confondus avec les numéros réguliers

### US-013.6: Extraire la qualité et le format
**En tant que** système,
**je veux** extraire la qualité et le format du fichier depuis le nom,
**afin de** alimenter le scoring et le profil de qualité.

**Critères d'acceptation :**
- [ ] Les qualités reconnues incluent : TruePDF, Retail, PDF-HQ, Scan, HQ, LQ
- [ ] Les formats reconnus incluent : PDF, EPUB, CBR, CBZ, MOBI
- [ ] Le groupe de release est extrait si présent (ex: le texte après le dernier tiret/point avant l'extension)
- [ ] Si la qualité n'est pas identifiable dans le nom, elle est marquée comme "Unknown"

## Functional Requirements

### FR-013.1: API de parsing
Le parser DOIT exposer une fonction qui accepte un nom de fichier et retourne un objet structuré avec tous les composants extraits.

### FR-013.2: Tests extensifs
Le parser DOIT être couvert par au minimum 25 cas de test couvrant tous les patterns décrits (conformément à l'Article III de la constitution).

### FR-013.3: Résultat structuré
Le résultat du parsing DOIT contenir : title (string), issue_number (int|null), volume (int|null), year (int|null), month (int|null), language (string|null), quality (string|null), format (string|null), is_special (bool), release_group (string|null), confidence (float 0-1).

### FR-013.4: Normalisation du titre
Le parser DOIT normaliser le titre extrait (minuscules, sans accents, sans ponctuation) pour le matching.

### FR-013.5: Extensibilité des patterns
Les patterns de reconnaissance DOIVENT être organisés de manière à faciliter l'ajout de nouveaux cas sans modifier la logique principale.

## Non-Functional Requirements

### NFR-013.1: Performance
Le parsing d'un nom de fichier unique DOIT se terminer en moins de 10 millisecondes.

### NFR-013.2: Robustesse
Le parser ne DOIT JAMAIS lever une exception non gérée. Tout nom de fichier, même absurde, DOIT produire un résultat (potentiellement avec tous les champs à "unknown/null").

## Edge Cases & Error Handling

- Un nom de fichier vide ou composé uniquement de l'extension retourne un résultat avec tous les champs à null/unknown.
- Un nom de fichier avec des caractères Unicode exotiques est traité en best-effort sans erreur.
- Un nom de fichier très long (> 500 caractères) est tronqué avant traitement.
- Un fichier avec une double extension (ex: "magazine.pdf.bak") utilise la dernière extension reconnue comme format.
- Un nom contenant des informations contradictoires (ex: deux numéros différents) utilise le premier trouvé.

## Out of Scope

- Parsing du contenu du fichier (OCR, extraction de texte)
- Interface de configuration des patterns de parsing
- Apprentissage automatique des patterns

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Foundation)
- Bloque : Feature 002 (Issue Tracking — scan import), Feature 006 (Post-Download Import — parsing)
