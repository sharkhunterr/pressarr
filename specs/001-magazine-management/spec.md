# Feature 001: Magazine Management

**Branch:** 001-magazine-management
**Date:** 2026-02-25
**Status:** Draft

## Overview

Permettre aux utilisateurs d'ajouter, consulter, modifier et supprimer des magazines dans leur bibliothèque Pressarr. C'est la feature centrale autour de laquelle gravitent toutes les autres fonctionnalités du système.

## User Stories

### US-001.1: Rechercher un magazine
**En tant que** utilisateur,
**je veux** rechercher un magazine par son titre via les sources de métadonnées,
**afin de** trouver le magazine que je souhaite ajouter à ma bibliothèque.

**Critères d'acceptation :**
- [ ] Un champ de recherche permet de saisir un titre de magazine
- [ ] Les résultats affichent le titre, l'éditeur, le pays et la couverture quand disponible
- [ ] Les résultats provenant de différentes sources sont agrégés et dédupliqués
- [ ] Si aucune source n'est disponible, un message d'erreur explicite est affiché
- [ ] Les magazines déjà dans la bibliothèque sont marqués visuellement dans les résultats

### US-001.2: Ajouter un magazine à la bibliothèque
**En tant que** utilisateur,
**je veux** ajouter un magazine à ma bibliothèque avec ses paramètres,
**afin de** commencer à surveiller et télécharger ses numéros.

**Critères d'acceptation :**
- [ ] L'utilisateur peut sélectionner un résultat de recherche et l'ajouter
- [ ] L'utilisateur peut ajouter manuellement un magazine non référencé (saisie manuelle du titre, fréquence, dossier)
- [ ] Lors de l'ajout, l'utilisateur configure : le dossier de destination, le profil de qualité, la fréquence de publication, et l'état de monitoring (activé/désactivé)
- [ ] Après l'ajout, le magazine apparaît dans la bibliothèque avec le statut approprié
- [ ] Un magazine ne peut pas être ajouté en double (même titre + même ISSN)
- [ ] L'utilisateur peut optionnellement déclencher une recherche automatique des numéros manquants à l'ajout

### US-001.3: Voir la bibliothèque de magazines
**En tant que** utilisateur,
**je veux** voir la liste de mes magazines dans une grille de couvertures,
**afin de** avoir une vue d'ensemble de ma collection.

**Critères d'acceptation :**
- [ ] Les magazines sont affichés dans une grille responsive (4 colonnes desktop, 2 tablette, 1 mobile)
- [ ] Chaque carte affiche la couverture (ratio 3:4), le titre et le nombre d'issues disponibles/totales
- [ ] Un badge de statut coloré indique l'état global du magazine (vert=complet, orange=issues manquantes, gris=non monitoré)
- [ ] Les magazines peuvent être triés (par titre, date d'ajout, prochaine parution)
- [ ] Les magazines peuvent être filtrés (par statut de monitoring, par complétude)
- [ ] Un état vide affiche un message invitant à ajouter un premier magazine

### US-001.4: Voir le détail d'un magazine
**En tant que** utilisateur,
**je veux** voir la page de détail d'un magazine,
**afin de** consulter ses informations et ses issues.

**Critères d'acceptation :**
- [ ] La page affiche les métadonnées du magazine (titre, éditeur, pays, ISSN, fréquence, description)
- [ ] La couverture est affichée en grand format
- [ ] La liste des issues connues est affichée (groupée par année — voir Feature 002)
- [ ] Les paramètres actuels du magazine sont visibles (dossier, profil qualité, monitoring)
- [ ] Un indicateur de progression affiche le ratio issues disponibles / issues totales

### US-001.5: Modifier les paramètres d'un magazine
**En tant que** utilisateur,
**je veux** modifier les paramètres d'un magazine existant,
**afin de** ajuster sa configuration sans le supprimer.

**Critères d'acceptation :**
- [ ] L'utilisateur peut modifier : le dossier de destination, le profil de qualité, la fréquence de publication, l'état de monitoring
- [ ] Les modifications sont sauvegardées immédiatement
- [ ] Un changement de dossier de destination propose optionnellement de déplacer les fichiers existants
- [ ] Les fichiers existants ne sont JAMAIS déplacés sans confirmation explicite de l'utilisateur

### US-001.6: Supprimer un magazine
**En tant que** utilisateur,
**je veux** supprimer un magazine de ma bibliothèque,
**afin de** ne plus le surveiller.

**Critères d'acceptation :**
- [ ] Une confirmation est demandée avant la suppression
- [ ] L'utilisateur peut choisir de supprimer uniquement l'entrée en base OU de supprimer aussi les fichiers sur le disque
- [ ] Après suppression, le magazine n'apparaît plus dans la bibliothèque
- [ ] Les téléchargements en cours pour ce magazine sont annulés

## Functional Requirements

### FR-001.1: CRUD Magazine
Le système DOIT permettre de créer, lire, mettre à jour et supprimer des magazines via l'API et l'interface web. L'ajout DOIT être possible soit via la recherche de métadonnées, soit manuellement (saisie du titre, de la fréquence et du dossier) pour les magazines non référencés dans les sources.

### FR-001.2: Recherche de métadonnées
Le système DOIT interroger les sources de métadonnées configurées pour trouver des magazines par titre, et agréger les résultats.

### FR-001.3: Unicité des magazines
Le système DOIT empêcher l'ajout d'un magazine déjà présent dans la bibliothèque (basé sur un identifiant unique : titre normalisé + ISSN si disponible).

### FR-001.4: Paramètres par magazine
Chaque magazine DOIT avoir ses propres paramètres configurables : dossier de destination, profil de qualité, fréquence de publication, état de monitoring.

### FR-001.5: API compatible *arr
Les endpoints magazine DOIVENT suivre le pattern /api/v1/magazine (GET liste, GET/:id détail, POST création, PUT/:id mise à jour, DELETE/:id suppression).

### FR-001.6: Compteurs de statut
La réponse API d'un magazine DOIT inclure les compteurs : nombre d'issues totales, nombre d'issues disponibles, nombre d'issues manquantes.

## Non-Functional Requirements

### NFR-001.1: Performance de la grille
La page bibliothèque DOIT afficher jusqu'à 200 magazines sans dégradation perceptible des performances.

### NFR-001.2: Recherche réactive
Les résultats de recherche de métadonnées DOIVENT s'afficher en moins de 5 secondes (hors latence réseau des fournisseurs).

## Edge Cases & Error Handling

- Si toutes les sources de métadonnées sont indisponibles lors d'une recherche, afficher un message explicite et ne pas bloquer l'application.
- Si un magazine n'a pas de couverture disponible, afficher un placeholder avec le titre.
- Si le dossier de destination d'un magazine n'existe pas, le créer automatiquement ou avertir l'utilisateur selon la configuration.
- Si la suppression des fichiers échoue (permissions), logger l'erreur et informer l'utilisateur des fichiers non supprimés.

## Out of Scope

- Gestion détaillée des issues individuelles (Feature 002)
- Récupération des métadonnées en profondeur (Feature 003)
- Recherche et téléchargement automatique (Feature 004)
- Profils de qualité (Feature 009)

## Clarifications

### Session 2026-02-25

- Q: L'ajout manuel d'un magazine (sans recherche de métadonnées) est-il souhaité ? → A: Oui, l'ajout manuel est autorisé (titre, fréquence, dossier saisis à la main) pour les magazines non référencés.

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Project Foundation)
- Bloque : Feature 002 (Issue Tracking), Feature 004 (Search & Download), Feature 007 (Calendar)
