# Feature 009: Quality Profiles

**Branch:** 009-quality-profiles
**Date:** 2026-02-25
**Status:** Draft

## Overview

Permettre aux utilisateurs de définir des profils de qualité pour contrôler quels fichiers sont acceptés et préférés lors de la recherche et du téléchargement. Chaque profil définit une hiérarchie de qualités et un seuil (cutoff) au-delà duquel les upgrades ne sont plus recherchées.

## User Stories

### US-009.1: Créer un profil de qualité
**En tant que** administrateur,
**je veux** créer un profil de qualité avec une hiérarchie de niveaux,
**afin de** définir mes préférences de qualité pour les magazines.

**Critères d'acceptation :**
- [ ] L'administrateur peut créer un profil avec un nom et une liste ordonnée de qualités
- [ ] Les niveaux de qualité prédéfinis incluent au minimum : Scan, PDF, PDF-HQ, Retail, TruePDF
- [ ] L'ordre de la liste définit la préférence (du moins bon au meilleur)
- [ ] L'administrateur peut activer/désactiver chaque niveau (un niveau désactivé est rejeté lors de la recherche)
- [ ] Un profil par défaut est créé au premier démarrage

### US-009.2: Définir un cutoff de qualité
**En tant que** administrateur,
**je veux** définir un seuil (cutoff) dans un profil de qualité,
**afin de** arrêter automatiquement les recherches quand une qualité suffisante est atteinte.

**Critères d'acceptation :**
- [ ] Chaque profil a un cutoff parmi les niveaux de qualité activés
- [ ] Une fois qu'une issue possède un fichier au niveau du cutoff ou supérieur, elle n'est plus recherchée
- [ ] Le cutoff est visuellement indiqué dans l'interface de configuration du profil
- [ ] Si le cutoff n'est pas défini, toute qualité acceptée satisfait la recherche

### US-009.3: Modifier et supprimer un profil
**En tant que** administrateur,
**je veux** modifier ou supprimer un profil de qualité existant,
**afin de** ajuster mes préférences au fil du temps.

**Critères d'acceptation :**
- [ ] Les modifications d'un profil sont immédiatement prises en compte pour les prochaines recherches
- [ ] Un profil ne peut pas être supprimé s'il est assigné à un ou plusieurs magazines
- [ ] Lors de la suppression, un message indique les magazines utilisant ce profil
- [ ] Le profil par défaut ne peut pas être supprimé, seulement modifié

### US-009.4: Appliquer le profil au scoring
**En tant que** système,
**je veux** utiliser le profil de qualité d'un magazine lors du scoring des résultats de recherche,
**afin de** ne proposer que les releases correspondant aux préférences de qualité.

**Critères d'acceptation :**
- [ ] Les résultats de recherche dont la qualité n'est pas dans les niveaux activés sont filtrés
- [ ] Les résultats sont pondérés par la position dans la hiérarchie (meilleure qualité = score plus élevé)
- [ ] Si aucun résultat ne correspond au profil, la recherche retourne 0 résultat (pas de fallback en dehors du profil)

### US-009.5: Upgrade automatique
**En tant que** système,
**je veux** remplacer automatiquement un fichier existant par un fichier de meilleure qualité,
**afin de** améliorer progressivement la collection.

**Critères d'acceptation :**
- [ ] Si une issue possède un fichier en dessous du cutoff et qu'une release de meilleure qualité est trouvée, elle est téléchargée
- [ ] Après import du nouveau fichier, l'ancien est supprimé (ou archivé selon la configuration)
- [ ] L'historique enregistre l'upgrade avec l'ancienne et la nouvelle qualité
- [ ] Les upgrades ne sont tentées que pour les issues en dessous du cutoff

## Functional Requirements

### FR-009.1: Définitions de qualité
Le système DOIT inclure un ensemble de définitions de qualité prédéfinies : Unknown, Scan, PDF, PDF-HQ, Retail, TruePDF. Chaque définition a un nom et un poids numérique.

### FR-009.2: CRUD Profils
Le système DOIT permettre de créer, lire, mettre à jour et supprimer des profils de qualité via l'API /api/v1/quality-profile.

### FR-009.3: Assignation par magazine
Chaque magazine DOIT avoir un profil de qualité assigné. Le profil par défaut est utilisé si non spécifié.

### FR-009.4: Détection de qualité
Le système DOIT être capable de déterminer la qualité d'un fichier à partir du nom de la release (mots-clés : TruePDF, Retail, Scan, HQ, etc.).

## Non-Functional Requirements

### NFR-009.1: Performance
L'application du profil de qualité au scoring DOIT ajouter moins de 100ms au temps de traitement d'une recherche.

## Edge Cases & Error Handling

- Si la qualité d'une release ne peut pas être déterminée, elle est classée comme "Unknown" et acceptée uniquement si "Unknown" est activé dans le profil.
- Si tous les niveaux de qualité sont désactivés dans un profil, le profil est considéré invalide et ne peut pas être sauvegardé.
- Si un magazine change de profil de qualité, les fichiers existants ne sont pas affectés rétroactivement.
- Si une upgrade échoue (téléchargement raté), l'ancien fichier est conservé.

## Out of Scope

- Qualité vidéo/audio (Pressarr ne gère que des fichiers magazine)
- Configuration de la détection de qualité par expressions régulières personnalisées
- Profils de qualité par issue (le profil est au niveau du magazine)

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Foundation)
- Bloque : Feature 004 (Search & Download — scoring), Feature 006 (Post-Download Import — upgrade)
