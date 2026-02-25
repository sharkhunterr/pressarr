# Feature 011: Activity & History

**Branch:** 011-activity-history
**Date:** 2026-02-25
**Status:** Draft

## Overview

Fournir une vue en temps réel de l'activité en cours (file de téléchargement) et un historique des événements passés (grab, download, import, erreur). Permettre la gestion d'une blocklist de releases rejetées.

## User Stories

### US-011.1: Voir la file d'attente en temps réel
**En tant que** utilisateur,
**je veux** voir la file d'attente des téléchargements en temps réel,
**afin de** suivre l'activité en cours de Pressarr.

**Critères d'acceptation :**
- [ ] La page d'activité affiche tous les téléchargements en cours et en attente
- [ ] Chaque entrée affiche : titre du magazine, numéro de l'issue, progression (%), vitesse, ETA, statut
- [ ] Les mises à jour sont en temps réel via WebSocket (pas de rechargement de page)
- [ ] L'ordre d'affichage est : en cours en premier, puis en attente par ordre d'ajout
- [ ] L'utilisateur peut annuler un téléchargement depuis cette page

### US-011.2: Voir l'historique des événements
**En tant que** utilisateur,
**je veux** voir l'historique des événements passés,
**afin de** comprendre ce qui s'est passé et diagnostiquer les problèmes.

**Critères d'acceptation :**
- [ ] L'historique affiche les événements : grabbed, downloaded, imported, failed, deleted
- [ ] Chaque événement affiche : date/heure, type, magazine, issue, détails (qualité, source, indexeur)
- [ ] L'historique est paginé (défaut : 50 événements par page)
- [ ] L'utilisateur peut filtrer par type d'événement, par magazine, par plage de dates
- [ ] L'utilisateur peut rechercher dans l'historique par texte libre
- [ ] Les événements d'erreur affichent le message d'erreur et le contexte

### US-011.3: Gérer la blocklist
**En tant que** utilisateur,
**je veux** voir et gérer la liste des releases bloquées,
**afin de** empêcher le re-téléchargement de releases problématiques.

**Critères d'acceptation :**
- [ ] La blocklist affiche toutes les releases rejetées avec : titre, indexeur, date de blocage, raison
- [ ] L'utilisateur peut débloquer une release (la retirer de la blocklist)
- [ ] Les releases sont automatiquement ajoutées à la blocklist quand un téléchargement/import échoue
- [ ] Les releases de la blocklist sont exclues des résultats de recherche futurs
- [ ] L'utilisateur peut vider entièrement la blocklist

### US-011.4: Mises à jour temps réel de la queue
**En tant que** dashboard externe,
**je veux** recevoir les mises à jour de la queue via WebSocket,
**afin de** afficher l'activité de Pressarr dans mon tableau de bord.

**Critères d'acceptation :**
- [ ] Une connexion WebSocket sur /ws permet de recevoir les mises à jour de la queue
- [ ] Les messages incluent : type d'événement (ajout, progression, complétion, suppression), données de l'élément
- [ ] La connexion supporte la reconnexion automatique côté client
- [ ] L'API REST /api/v1/queue retourne un snapshot de la queue pour l'état initial

## Functional Requirements

### FR-011.1: Modèle d'événement
Chaque événement DOIT contenir : identifiant unique, type (grabbed, downloaded, imported, failed, deleted), référence au magazine, référence à l'issue, détails (release, source, qualité, message d'erreur), horodatage.

### FR-011.2: Rétention de l'historique
L'historique DOIT conserver les événements selon une politique de rétention configurable (défaut : 90 jours). Les événements plus anciens sont automatiquement supprimés.

### FR-011.3: Blocklist persistante
La blocklist DOIT être persistée en base de données et consultée à chaque recherche.

### FR-011.4: API compatible *arr
Les endpoints DOIVENT suivre les patterns : /api/v1/queue (file d'attente), /api/v1/history (historique), /api/v1/blocklist (liste noire).

### FR-011.5: WebSocket pour la queue
Les changements de la file d'attente DOIVENT être diffusés via WebSocket à tous les clients connectés.

## Non-Functional Requirements

### NFR-011.1: Performance de l'historique
La consultation de l'historique avec filtres DOIT retourner des résultats en moins de 2 secondes, même avec 10 000 événements.

### NFR-011.2: Latence WebSocket
Les mises à jour WebSocket DOIVENT être transmises en moins de 1 seconde après le changement d'état.

## Edge Cases & Error Handling

- Si le WebSocket se déconnecte, le client DOIT pouvoir se reconnecter et récupérer l'état actuel via l'API REST.
- Si la base de données atteint la limite de rétention, les plus anciens événements sont purgés automatiquement en arrière-plan.
- Si un événement concerne un magazine/issue supprimé, les informations sont conservées dans l'historique (pas de suppression en cascade).
- Si la blocklist contient une release qui n'existe plus sur les indexeurs, elle est conservée (nettoyage manuel uniquement).

## Out of Scope

- Statistiques avancées et graphiques (dashboard analytique)
- Export de l'historique en fichier
- Notifications (Feature 010 — lié mais séparé)

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Foundation), Feature 004 (Search — événements grab), Feature 005 (Download Clients — événements download)
- Bloque : Aucune
