# Feature 010: Notifications

**Branch:** 010-notifications
**Date:** 2026-02-25
**Status:** Draft

## Overview

Alerter l'utilisateur des événements importants de Pressarr via différents canaux de notification (Discord, Gotify, Telegram, webhook générique). L'utilisateur choisit quels événements déclenchent une notification et sur quels canaux.

## User Stories

### US-010.1: Configurer un webhook Discord
**En tant que** administrateur,
**je veux** configurer un webhook Discord,
**afin de** recevoir les notifications de Pressarr dans un canal Discord.

**Critères d'acceptation :**
- [ ] L'administrateur peut saisir l'URL du webhook Discord
- [ ] Un bouton "Test" envoie une notification de test et affiche le résultat
- [ ] Les notifications Discord incluent un embed riche avec la couverture du magazine si disponible
- [ ] Si le webhook est invalide ou injoignable, un message d'erreur explicite est affiché

### US-010.2: Configurer Gotify
**En tant que** administrateur,
**je veux** configurer un serveur Gotify,
**afin de** recevoir les notifications via Gotify.

**Critères d'acceptation :**
- [ ] L'administrateur peut saisir l'URL du serveur et le token d'application
- [ ] Un bouton "Test" envoie une notification de test
- [ ] Les notifications Gotify incluent le titre et le corps du message avec les détails pertinents
- [ ] La priorité Gotify est configurable

### US-010.3: Configurer Telegram
**En tant que** administrateur,
**je veux** configurer un bot Telegram,
**afin de** recevoir les notifications via Telegram.

**Critères d'acceptation :**
- [ ] L'administrateur peut saisir le token du bot et le chat ID
- [ ] Un bouton "Test" envoie un message de test
- [ ] Les notifications Telegram incluent le texte formaté et la couverture si disponible
- [ ] Si le chat ID est invalide, un message d'erreur explicite est affiché

### US-010.4: Configurer un webhook générique
**En tant que** administrateur,
**je veux** configurer un webhook HTTP générique,
**afin de** intégrer Pressarr avec n'importe quel service supportant les webhooks.

**Critères d'acceptation :**
- [ ] L'administrateur peut saisir : URL, méthode HTTP (POST/PUT), headers personnalisés
- [ ] Un bouton "Test" envoie une requête de test
- [ ] Le corps de la requête contient un payload JSON structuré avec les détails de l'événement
- [ ] Les headers personnalisés permettent l'authentification (Bearer token, API key, etc.)

### US-010.5: Choisir les événements déclencheurs
**En tant que** administrateur,
**je veux** choisir quels événements déclenchent une notification sur chaque canal,
**afin de** ne recevoir que les alertes pertinentes.

**Critères d'acceptation :**
- [ ] Les événements disponibles sont : grab (release envoyée au client), download (fichier téléchargé), import (fichier importé dans la bibliothèque), error (erreur critique)
- [ ] Chaque canal de notification peut être configuré indépendamment pour chaque type d'événement
- [ ] Par défaut, tous les événements sont activés sur un nouveau canal
- [ ] Les changements de configuration sont pris en compte immédiatement

### US-010.6: Contenu des notifications
**En tant que** utilisateur,
**je veux** que les notifications contiennent les informations pertinentes,
**afin de** comprendre immédiatement ce qui s'est passé.

**Critères d'acceptation :**
- [ ] Les notifications incluent : titre du magazine, numéro de l'issue, type d'événement
- [ ] Les notifications d'import incluent la qualité du fichier
- [ ] Les notifications incluent la couverture du magazine quand le canal le supporte
- [ ] Les notifications d'erreur incluent un résumé de l'erreur et le contexte (magazine/issue concerné)

## Functional Requirements

### FR-010.1: Interface de notification abstraite
Chaque canal de notification DOIT implémenter une interface commune permettant d'ajouter de nouveaux canaux sans modifier le code existant.

### FR-010.2: CRUD Canaux
Le système DOIT permettre de créer, lire, mettre à jour et supprimer des canaux de notification via l'API /api/v1/notification.

### FR-010.3: Envoi asynchrone
L'envoi des notifications DOIT être asynchrone et ne DOIT JAMAIS bloquer ou retarder le processus principal (import, téléchargement, etc.).

### FR-010.4: Payload structuré
Chaque notification DOIT contenir un payload JSON structuré avec : eventType, magazine (titre, id), issue (numéro, date), quality (si applicable), timestamp.

### FR-010.5: Retry sur échec
Si l'envoi d'une notification échoue, le système DOIT réessayer jusqu'à 3 fois avec un backoff exponentiel.

## Non-Functional Requirements

### NFR-010.1: Non-bloquant
L'échec d'envoi d'une notification ne DOIT JAMAIS impacter le fonctionnement normal de Pressarr.

### NFR-010.2: Latence
Les notifications DOIVENT être envoyées dans les 30 secondes suivant l'événement déclencheur.

## Edge Cases & Error Handling

- Si un canal de notification est supprimé alors qu'une notification est en file d'attente, la notification est annulée.
- Si tous les retry échouent, l'erreur est loguée et aucune notification supplémentaire n'est tentée pour cet événement.
- Si un webhook retourne un code HTTP 4xx (erreur client), les retry ne sont pas tentés (erreur permanente).
- Si un webhook retourne un code HTTP 5xx (erreur serveur), les retry sont tentés.
- Si la couverture n'est pas disponible, la notification est envoyée sans image.

## Out of Scope

- Configuration des canaux dans l'UI (Feature 012)
- Notifications par email
- Notifications push navigateur
- Historique des notifications envoyées

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Foundation)
- Bloque : Feature 006 (Post-Download Import — envoi de notifications)
