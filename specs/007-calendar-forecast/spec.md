# Feature 007: Calendar & Forecast

**Branch:** 007-calendar-forecast
**Date:** 2026-02-25
**Status:** Draft

## Overview

Prédire les futures parutions de magazines basé sur leur fréquence de publication et afficher un calendrier combinant les issues confirmées et les prévisions. Permettre la réconciliation automatique quand un numéro prédit est effectivement obtenu.

## User Stories

### US-007.1: Afficher le calendrier mensuel
**En tant que** utilisateur,
**je veux** voir un calendrier mensuel avec les issues passées et futures,
**afin de** savoir quand mes magazines paraissent et planifier mes attentes.

**Critères d'acceptation :**
- [ ] Un calendrier mensuel affiche les jours avec des indicateurs d'issues
- [ ] Les issues confirmées (téléchargées) sont visuellement distinctes des prévisions
- [ ] La navigation entre les mois est possible (précédent/suivant, sélection directe)
- [ ] Chaque entrée du calendrier affiche le titre du magazine et le numéro
- [ ] Un clic sur une entrée mène à la page de détail de l'issue

### US-007.2: Générer les prévisions automatiquement
**En tant que** système,
**je veux** générer automatiquement des prévisions de parution basées sur la fréquence,
**afin de** anticiper les futures issues à rechercher.

**Critères d'acceptation :**
- [ ] Les prévisions sont générées pour les 6 prochains mois (magazines mensuels et moins fréquents) ou 8 prochaines semaines (hebdomadaires)
- [ ] Les fréquences supportées sont : weekly, biweekly, monthly, bimonthly, quarterly, annual
- [ ] Les prévisions sont recalculées quand la fréquence d'un magazine est modifiée
- [ ] Les prévisions utilisent la date de la dernière issue connue comme point de départ
- [ ] Les prévisions portent un statut "upcoming" distinct des issues confirmées

### US-007.3: Distinguer visuellement les types d'issues
**En tant que** utilisateur,
**je veux** distinguer visuellement les issues téléchargées des prévisions dans le calendrier,
**afin de** savoir immédiatement ce que j'ai et ce qui est attendu.

**Critères d'acceptation :**
- [ ] Les issues disponibles (downloaded) utilisent le badge vert standard
- [ ] Les prévisions (upcoming) utilisent le badge gris
- [ ] Les issues voulues (wanted) utilisent le badge orange
- [ ] Les issues en cours de téléchargement utilisent le badge bleu
- [ ] Une légende est accessible pour rappeler la signification des couleurs

### US-007.4: Réconcilier automatiquement les prévisions
**En tant que** système,
**je veux** réconcilier automatiquement une prévision quand l'issue correspondante est téléchargée,
**afin de** maintenir le calendrier à jour sans intervention manuelle.

**Critères d'acceptation :**
- [ ] Quand une issue est importée, le système cherche une prévision correspondante (même magazine, date proche)
- [ ] Si un match est trouvé, la prévision est remplacée par l'issue réelle
- [ ] La tolérance de matching est de +/- 15 jours par rapport à la date prédite
- [ ] Si aucune prévision ne correspond, l'issue est simplement ajoutée au calendrier

### US-007.5: Marquer une prévision comme retardée
**En tant que** système,
**je veux** marquer automatiquement une prévision comme "retardée" si la date est dépassée,
**afin de** signaler les magazines potentiellement en retard de publication.

**Critères d'acceptation :**
- [ ] Une prévision dont la date est dépassée de plus de 7 jours est marquée comme "retardée"
- [ ] Le badge visuel change pour indiquer le retard (orange clignotant ou icône spécifique)
- [ ] Le délai de grâce est configurable (défaut : 7 jours)
- [ ] Les prévisions retardées sont listées dans un résumé accessible depuis la page d'accueil

### US-007.6: Skip une prévision
**En tant que** utilisateur,
**je veux** marquer une prévision comme "skippée",
**afin d'** indiquer que je ne souhaite pas obtenir ce numéro.

**Critères d'acceptation :**
- [ ] L'utilisateur peut cliquer sur une prévision pour la marquer comme "skipped"
- [ ] Une prévision skippée affiche le badge gris avec un indicateur visuel distinct
- [ ] Une prévision skippée n'est pas recherchée automatiquement
- [ ] L'utilisateur peut annuler le skip pour remettre la prévision en "upcoming"

## Functional Requirements

### FR-007.1: Calcul de prévision
Le système DOIT calculer les dates de parution futures en fonction de la fréquence configurée et de la date de la dernière issue connue.

### FR-007.2: Fréquences supportées
Le système DOIT supporter les fréquences suivantes : weekly (7 jours), biweekly (14 jours), monthly (1 mois), bimonthly (2 mois), quarterly (3 mois), annual (12 mois).

### FR-007.3: Régénération des prévisions
Les prévisions DOIVENT être régénérées automatiquement quand : une issue est importée, la fréquence du magazine change, un rafraîchissement planifié est déclenché.

### FR-007.4: API Calendar
L'endpoint /api/v1/calendar DOIT retourner les issues et prévisions pour une plage de dates donnée, compatible avec les widgets de dashboard externe.

### FR-007.5: Persistance des prévisions
Les prévisions DOIVENT être persistées en base de données (pas recalculées à chaque affichage) pour permettre le suivi des retards et des skips.

## Non-Functional Requirements

### NFR-007.1: Performance du calendrier
L'affichage d'un mois de calendrier DOIT se faire en moins de 1 seconde, même avec 50 magazines monitorés.

### NFR-007.2: Compatibilité widgets
L'endpoint /api/v1/calendar DOIT être compatible avec les widgets calendrier de Homepage et Homarr.

## Edge Cases & Error Handling

- Si un magazine n'a aucune issue connue (vient d'être ajouté), les prévisions se basent sur la date d'aujourd'hui comme premier point.
- Si la fréquence d'un magazine est inconnue, aucune prévision n'est générée et un avertissement est affiché.
- Si un magazine cesse de paraître (aucune nouvelle issue depuis plus de 2x la fréquence attendue), un avertissement est affiché.
- Si deux prévisions tombent le même jour pour le même magazine (changement de fréquence), la plus récente est conservée.

## Out of Scope

- Recherche automatique des issues prédites (Feature 004)
- Notifications de parution (Feature 010)
- Configuration de la fréquence dans l'UI (Feature 001 et Feature 012)

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Foundation), Feature 001 (Magazine Management)
- Bloque : Aucune
