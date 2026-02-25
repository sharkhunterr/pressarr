# Feature 005: Download Clients Integration

**Branch:** 005-download-clients
**Date:** 2026-02-25
**Status:** Draft

## Overview

Intégrer les clients de téléchargement (torrent et usenet) pour envoyer des fichiers, suivre leur progression et détecter leur complétion. Pressarr supporte plusieurs clients simultanément, avec un client actif par protocole. Clients torrent supportés en V1 : Deluge, qBittorrent, Transmission. Clients usenet supportés en V1 : SABnzbd, NZBGet.

## User Stories

### US-005.1: Configurer un client torrent
**En tant que** administrateur,
**je veux** configurer un client torrent (Deluge, qBittorrent, Transmission),
**afin de** permettre le téléchargement de magazines via torrent.

**Critères d'acceptation :**
- [ ] L'administrateur peut ajouter un client torrent en choisissant son type
- [ ] Les champs de configuration varient selon le type (URL, credentials, certificat SSL...)
- [ ] Un bouton "Test" vérifie la connexion au client et affiche le résultat
- [ ] Plusieurs clients peuvent être configurés mais un seul est actif par protocole
- [ ] Les credentials sont stockés de manière sécurisée (jamais affichés en clair après saisie)

### US-005.2: Configurer un client usenet
**En tant que** administrateur,
**je veux** configurer un client usenet (SABnzbd, NZBGet),
**afin de** permettre le téléchargement de magazines via usenet.

**Critères d'acceptation :**
- [ ] L'administrateur peut ajouter un client usenet en choisissant son type
- [ ] Les champs de configuration incluent URL et clé API ou credentials selon le client
- [ ] Un bouton "Test" vérifie la connexion
- [ ] Plusieurs clients peuvent être configurés mais un seul est actif par protocole

### US-005.3: Envoyer un téléchargement
**En tant que** système,
**je veux** envoyer un torrent ou un NZB au client de téléchargement actif,
**afin de** démarrer le téléchargement d'une release.

**Critères d'acceptation :**
- [ ] Le système envoie un lien magnet, un fichier .torrent ou un fichier .nzb selon le type
- [ ] Le label/catégorie "pressarr" est systématiquement appliqué
- [ ] Le dossier de destination configuré est transmis au client si supporté
- [ ] L'identifiant du téléchargement retourné par le client est stocké pour le suivi
- [ ] Si aucun client n'est configuré pour le protocole requis, une erreur explicite est retournée

### US-005.4: Suivre la progression
**En tant que** utilisateur,
**je veux** suivre la progression des téléchargements en cours (vitesse, ETA, %),
**afin de** savoir quand mes fichiers seront disponibles.

**Critères d'acceptation :**
- [ ] Le système interroge périodiquement le client pour récupérer l'état des téléchargements labellés "pressarr"
- [ ] Les informations affichées incluent : progression (%), vitesse de téléchargement, ETA, taille totale
- [ ] Les mises à jour sont transmises en temps réel à l'interface via WebSocket
- [ ] Les téléchargements terminés sont détectés et signalés

### US-005.5: Détecter la complétion
**En tant que** système,
**je veux** détecter quand un téléchargement est terminé,
**afin de** déclencher le pipeline d'import post-téléchargement.

**Critères d'acceptation :**
- [ ] Le système détecte le passage du statut "downloading" à "completed" côté client
- [ ] Le chemin du fichier téléchargé est récupéré depuis le client
- [ ] Un événement de complétion est émis pour déclencher le post-traitement
- [ ] Si le téléchargement échoue côté client, l'issue est repassée en "wanted"

### US-005.6: Supprimer/annuler un téléchargement
**En tant que** utilisateur,
**je veux** supprimer ou annuler un téléchargement en cours,
**afin de** libérer de la bande passante ou corriger une erreur.

**Critères d'acceptation :**
- [ ] L'utilisateur peut annuler un téléchargement en cours depuis l'interface
- [ ] L'annulation supprime le téléchargement côté client et les fichiers partiels
- [ ] L'issue associée repasse au statut "wanted"
- [ ] Un événement d'annulation est enregistré dans l'historique

## Functional Requirements

### FR-005.1: Interface de client abstraite
Chaque type de client de téléchargement DOIT implémenter une interface commune : envoyer, lister, obtenir statut, supprimer.

### FR-005.2: Label/catégorie systématique
TOUS les téléchargements envoyés par Pressarr DOIVENT porter le label/catégorie "pressarr".

### FR-005.3: Un client actif par protocole
Le système DOIT supporter un client actif par protocole (un torrent, un usenet). Les clients inactifs sont conservés en configuration mais pas utilisés.

### FR-005.4: Polling de statut
Le système DOIT interroger les clients actifs à intervalle régulier (configurable, défaut : 30 secondes) pour mettre à jour l'état des téléchargements.

### FR-005.5: API Download Clients
Les endpoints DOIVENT suivre le pattern /api/v1/download-client pour la gestion et /api/v1/queue pour la file d'attente.

## Non-Functional Requirements

### NFR-005.1: Résilience
L'indisponibilité temporaire d'un client de téléchargement ne DOIT JAMAIS crasher Pressarr. Le polling continue avec des logs d'avertissement.

### NFR-005.2: Sécurité des credentials
Les mots de passe et clés API des clients DOIVENT être stockés de manière sécurisée et ne DOIVENT JAMAIS apparaître dans les logs.

## Edge Cases & Error Handling

- Si le client de téléchargement est redémarré, Pressarr DOIT retrouver les téléchargements en cours via le label "pressarr".
- Si un téléchargement reste bloqué (pas de progression pendant 1 heure), un avertissement est émis.
- Si le client refuse la connexion après configuration réussie, le polling continue de tenter la reconnexion.
- Si le label "pressarr" n'existe pas côté client, il DOIT être créé automatiquement si le client le supporte.
- Si le dossier de téléchargement configuré n'est pas accessible, une erreur explicite est retournée.

## Out of Scope

- Choix et envoi des releases (Feature 004)
- Traitement post-téléchargement (Feature 006)
- Téléchargement direct HTTP depuis Internet Archive (Feature 008)
- Interface de configuration des clients dans le navigateur (Feature 012)

## Clarifications

### Session 2026-02-25

- Q: Transmission doit-il être supporté dès la V1 ? → A: Oui, Transmission est supporté dès la V1 aux côtés de Deluge et qBittorrent.

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Project Foundation)
- Bloque : Feature 004 (Search & Download Pipeline), Feature 006 (Post-Download Import)
