# Feature 004: Search & Download Pipeline

**Branch:** 004-search-download-pipeline
**Date:** 2026-02-25
**Status:** Draft

## Overview

Chercher des releases de magazines via Prowlarr (indexeur), scorer et classer les résultats, et envoyer la meilleure release au client de téléchargement configuré. Cette feature est le coeur du pipeline automatisé de Pressarr.

## User Stories

### US-004.1: Configurer la connexion Prowlarr
**En tant que** administrateur,
**je veux** configurer la connexion à Prowlarr (URL, clé API),
**afin de** permettre à Pressarr de rechercher des releases via les indexeurs.

**Critères d'acceptation :**
- [ ] L'administrateur peut saisir l'URL et la clé API de Prowlarr
- [ ] Un bouton "Test" vérifie la connexion et affiche le résultat (succès/échec avec message)
- [ ] La configuration est persistée et utilisée pour toutes les recherches
- [ ] Si Prowlarr n'est pas configuré, les fonctions de recherche sont désactivées avec un message explicatif

### US-004.2: Rechercher manuellement une issue
**En tant que** utilisateur,
**je veux** lancer une recherche manuelle pour une issue spécifique,
**afin de** trouver et télécharger un numéro précis.

**Critères d'acceptation :**
- [ ] Depuis la page d'une issue, un bouton permet de lancer une recherche manuelle
- [ ] Les résultats affichent : titre de la release, indexeur, qualité détectée, taille, nombre de seeds/peers (torrents) ou âge (usenet), source
- [ ] Les résultats sont triés par score de pertinence (meilleur en premier)
- [ ] L'utilisateur peut choisir manuellement quelle release télécharger
- [ ] L'utilisateur peut aussi laisser le système choisir automatiquement la meilleure release

### US-004.3: Rechercher automatiquement les issues manquantes
**En tant que** système,
**je veux** rechercher automatiquement toutes les issues manquantes et monitorées d'un magazine,
**afin de** compléter la collection sans intervention manuelle.

**Critères d'acceptation :**
- [ ] La recherche automatique cible uniquement les issues au statut "wanted"
- [ ] Chaque issue est recherchée individuellement sur tous les indexeurs configurés
- [ ] Si une release convenable est trouvée, elle est envoyée automatiquement au client de téléchargement
- [ ] Le nombre de recherches simultanées est limité pour ne pas surcharger les indexeurs
- [ ] Un journal de recherche indique quelles issues ont été trouvées et lesquelles non

### US-004.4: Scorer et classer les résultats
**En tant que** système,
**je veux** scorer et classer les résultats de recherche selon plusieurs critères,
**afin de** sélectionner automatiquement la meilleure release disponible.

**Critères d'acceptation :**
- [ ] Le score prend en compte : correspondance du titre, qualité par rapport au profil, nombre de seeds (torrents), âge de la release (usenet), taille du fichier
- [ ] Les releases ne correspondant pas au titre du magazine sont exclues
- [ ] Les releases blacklistées sont exclues
- [ ] Le profil de qualité du magazine est appliqué pour filtrer et pondérer
- [ ] Le classement final est déterministe (même entrées = même ordre)

### US-004.5: Envoyer au client de téléchargement
**En tant que** système,
**je veux** envoyer la meilleure release au client de téléchargement configuré,
**afin de** lancer le téléchargement automatiquement.

**Critères d'acceptation :**
- [ ] La release est envoyée au client de téléchargement actif (torrent ou usenet)
- [ ] Le label/catégorie "pressarr" est appliqué au téléchargement
- [ ] L'issue passe au statut "snatched" après l'envoi réussi
- [ ] Un événement "grabbed" est enregistré dans l'historique
- [ ] Si l'envoi échoue, une notification d'erreur est émise et l'issue reste en "wanted"

### US-004.6: Synchroniser les flux RSS
**En tant que** système,
**je veux** synchroniser les flux RSS de Prowlarr à intervalle régulier,
**afin de** détecter automatiquement les nouvelles releases dès leur parution.

**Critères d'acceptation :**
- [ ] Un sync RSS est déclenché à intervalle configurable (défaut : 15 minutes)
- [ ] Les nouvelles releases sont matchées contre les issues "wanted" de tous les magazines
- [ ] Si un match est trouvé et que la release passe le scoring, elle est envoyée automatiquement
- [ ] Le sync continue même si le traitement d'une release échoue
- [ ] Le dernier sync réussi est affiché dans l'interface

### US-004.7: Surveiller les téléchargements en cours
**En tant que** utilisateur,
**je veux** voir la progression des téléchargements en cours,
**afin de** savoir quand mes magazines seront disponibles.

**Critères d'acceptation :**
- [ ] La liste des téléchargements en cours est visible dans l'interface
- [ ] Chaque téléchargement affiche : titre, progression (%), vitesse, ETA
- [ ] Les mises à jour de progression sont en temps réel
- [ ] L'issue liée est identifiable pour chaque téléchargement

## Functional Requirements

### FR-004.1: Communication Prowlarr
Le système DOIT communiquer avec Prowlarr via son API pour les recherches et le RSS, en utilisant la catégorie 7020 (Magazines) par défaut.

### FR-004.2: Algorithme de scoring
Le système DOIT scorer chaque résultat de recherche selon : correspondance titre (poids élevé), qualité vs profil (poids moyen), disponibilité seeds/âge (poids faible), taille fichier (poids faible).

### FR-004.3: Commande asynchrone de recherche
Les recherches automatiques DOIVENT être déclenchées via le pattern POST /api/v1/command compatible avec l'écosystème *arr.

### FR-004.4: Intervalle RSS configurable
L'intervalle de synchronisation RSS DOIT être configurable et avoir une valeur par défaut de 15 minutes.

### FR-004.5: Historique de grab
Chaque envoi au client de téléchargement DOIT être enregistré avec : release choisie, indexeur source, score, date/heure.

## Non-Functional Requirements

### NFR-004.1: Respect des indexeurs
Les recherches DOIVENT respecter les rate limits des indexeurs et ne pas envoyer plus de requêtes que nécessaire.

### NFR-004.2: Résilience Prowlarr
Si Prowlarr est indisponible, les recherches manuelles DOIVENT retourner une erreur explicite et les tâches planifiées DOIVENT être reportées.

## Edge Cases & Error Handling

- Si Prowlarr retourne 0 résultat pour une recherche, l'issue reste en "wanted" sans erreur.
- Si le client de téléchargement est indisponible au moment du grab, l'erreur est loguée et l'issue reste en "wanted".
- Si une release est envoyée mais que le téléchargement échoue côté client, le système DOIT détecter l'échec et repasser l'issue en "wanted".
- Si le RSS retourne des releases déjà traitées, elles sont silencieusement ignorées.
- Si la catégorie 7020 n'est pas configurée dans Prowlarr, un message d'avertissement est affiché.

## Out of Scope

- Configuration des indexeurs individuels (c'est le rôle de Prowlarr)
- Implémentation des clients de téléchargement (Feature 005)
- Traitement post-téléchargement (Feature 006)
- Profils de qualité (Feature 009, utilisés ici mais définis là-bas)

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Foundation), Feature 001 (Magazine), Feature 005 (Download Clients), Feature 009 (Quality Profiles)
- Bloque : Feature 006 (Post-Download Import), Feature 011 (Activity & History)
