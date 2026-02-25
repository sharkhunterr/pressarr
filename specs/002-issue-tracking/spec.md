# Feature 002: Issue Tracking & File Management

**Branch:** 002-issue-tracking
**Date:** 2026-02-25
**Status:** Draft

## Overview

Gérer les numéros individuels (issues) d'un magazine et les fichiers physiques associés. Chaque magazine est composé d'issues qui peuvent être voulues, possédées ou manquantes. Les fichiers peuvent être importés manuellement, scannés depuis le disque, renommés et organisés.

## User Stories

### US-002.1: Lister les issues d'un magazine
**En tant que** utilisateur,
**je veux** voir toutes les issues d'un magazine groupées par année,
**afin de** avoir une vue d'ensemble de la collection pour ce titre.

**Critères d'acceptation :**
- [ ] Les issues sont listées et groupées par année de publication
- [ ] Chaque issue affiche : numéro, date de publication, statut (available/wanted/missing/snatched/downloading)
- [ ] Un badge de statut coloré est affiché selon le code couleur standard (vert=available, orange=wanted, rouge=missing, violet=snatched, bleu=downloading)
- [ ] Le nombre d'issues par année est affiché dans l'en-tête de chaque groupe
- [ ] L'utilisateur peut déplier/replier les groupes par année

### US-002.2: Gérer le monitoring des issues
**En tant que** utilisateur,
**je veux** marquer des issues comme "monitored" (voulues) ou non,
**afin de** contrôler précisément quels numéros je souhaite obtenir.

**Critères d'acceptation :**
- [ ] L'utilisateur peut activer/désactiver le monitoring sur une issue individuelle
- [ ] L'utilisateur peut activer/désactiver le monitoring sur toutes les issues d'une année en un clic
- [ ] L'utilisateur peut activer/désactiver le monitoring sur toutes les issues du magazine en un clic
- [ ] Les issues non monitorées ne sont pas recherchées automatiquement
- [ ] Le changement de statut de monitoring est reflété immédiatement dans l'interface

### US-002.3: Importer un fichier manuellement
**En tant que** utilisateur,
**je veux** importer un fichier magazine existant et le rattacher à une issue,
**afin de** compléter ma collection avec des fichiers déjà en ma possession.

**Critères d'acceptation :**
- [ ] L'utilisateur peut sélectionner un fichier depuis le système de fichiers du serveur
- [ ] Le système propose automatiquement un rattachement à une issue basé sur le nom de fichier
- [ ] L'utilisateur peut confirmer ou corriger le rattachement proposé
- [ ] Le fichier est traité selon la politique d'import globale configurée (copier / déplacer / copier+supprimer, défaut = copier) puis renommé selon le template
- [ ] L'issue passe au statut "available" après l'import réussi

### US-002.4: Scanner un dossier pour détecter des fichiers existants
**En tant que** utilisateur,
**je veux** scanner un dossier pour détecter des fichiers magazine existants,
**afin de** importer en masse ma collection existante.

**Critères d'acceptation :**
- [ ] L'utilisateur peut sélectionner un dossier à scanner
- [ ] Le scan détecte les fichiers au format magazine (PDF, CBR, CBZ, EPUB)
- [ ] Chaque fichier détecté est proposé avec un rattachement automatique à un magazine et une issue
- [ ] L'utilisateur peut valider, corriger ou ignorer chaque proposition
- [ ] Un résumé post-scan indique : fichiers trouvés, fichiers rattachés, fichiers non reconnus

### US-002.5: Renommer et organiser les fichiers
**En tant que** utilisateur,
**je veux** que les fichiers soient renommés et déplacés selon un template configurable,
**afin de** avoir une bibliothèque organisée de manière cohérente.

**Critères d'acceptation :**
- [ ] Un template de nommage est appliqué à tous les fichiers (import manuel, téléchargement, scan)
- [ ] Le template supporte les variables : titre du magazine, numéro, année, mois, qualité, format
- [ ] Les fichiers sont placés dans un sous-dossier par magazine dans le dossier bibliothèque
- [ ] Un aperçu du nom final est affiché avant toute opération de renommage
- [ ] Les caractères interdits dans les noms de fichier sont automatiquement remplacés

### US-002.6: Supprimer un fichier d'issue
**En tant que** utilisateur,
**je veux** supprimer le fichier associé à une issue,
**afin de** libérer de l'espace ou remplacer un fichier de mauvaise qualité.

**Critères d'acceptation :**
- [ ] Une confirmation est demandée avant la suppression
- [ ] Le fichier est supprimé du disque
- [ ] L'issue repasse au statut "wanted" (si monitorée) ou "missing" (si non monitorée)
- [ ] L'événement de suppression est enregistré dans l'historique

## Functional Requirements

### FR-002.1: Modèle Issue
Chaque issue DOIT avoir : un identifiant unique, une référence au magazine parent, un numéro et/ou une date de publication, un statut (wanted, available, missing, snatched, downloading, skipped), et un état de monitoring.

### FR-002.2: Modèle IssueFile
Chaque fichier associé à une issue DOIT avoir : un chemin sur le disque, un format (PDF, CBR, CBZ, EPUB), une qualité, une taille, et une date d'import.

### FR-002.3: Template de nommage
Le système DOIT appliquer un template de nommage configurable lors de l'import ou du renommage de fichiers. Le template DOIT supporter au minimum : {titre}, {numero}, {annee}, {mois}, {qualite}, {format}.

### FR-002.4: Scan de dossier
Le scan DOIT parcourir récursivement un dossier donné et identifier les fichiers au format magazine supporté.

### FR-002.5: API Issues
Les endpoints DOIVENT suivre le pattern /api/v1/magazine/:id/issue pour la liste et /api/v1/issue/:id pour les opérations individuelles.

## Non-Functional Requirements

### NFR-002.1: Performance du scan
Le scan d'un dossier contenant 1000 fichiers DOIT se terminer en moins de 60 secondes.

### NFR-002.2: Intégrité des fichiers
Le déplacement/renommage de fichiers DOIT être atomique : en cas d'erreur, le fichier original DOIT rester intact.

## Edge Cases & Error Handling

- Si un fichier est verrouillé par un autre processus lors du renommage/déplacement, l'opération DOIT échouer proprement avec un message explicite.
- Si le disque est plein lors d'une copie, l'opération DOIT être annulée et le fichier partiel nettoyé.
- Si un fichier scanné ne correspond à aucun magazine connu, il DOIT être listé comme "non reconnu" sans erreur.
- Si une issue a déjà un fichier et qu'un nouveau fichier est importé, l'utilisateur DOIT confirmer le remplacement.

## Out of Scope

- Parser de noms de fichiers (Feature 013)
- Pipeline de post-téléchargement automatique (Feature 006)
- Template de nommage UI de configuration (Feature 012)

## Clarifications

### Session 2026-02-25

- Q: Les fichiers originaux doivent-ils être copiés ou déplacés lors de l'import manuel ? → A: Même politique configurable que le post-import (copier / déplacer / copier+supprimer, défaut = copier). Un seul paramètre global pour tout Pressarr.

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Project Foundation), Feature 001 (Magazine Management)
- Bloque : Feature 006 (Post-Download Import)
