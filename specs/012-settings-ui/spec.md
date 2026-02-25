# Feature 012: Settings UI

**Branch:** 012-settings-ui
**Date:** 2026-02-25
**Status:** Draft

## Overview

Fournir une interface complète de configuration dans le navigateur permettant de gérer tous les aspects de Pressarr : médias, indexeurs, clients de téléchargement, notifications, métadonnées, qualité et paramètres généraux. L'objectif est que l'administrateur n'ait jamais à modifier manuellement le fichier de configuration.

## User Stories

### US-012.1: Configurer la gestion des médias
**En tant que** administrateur,
**je veux** configurer le template de nommage et les dossiers racine depuis l'interface,
**afin de** contrôler l'organisation de ma bibliothèque.

**Critères d'acceptation :**
- [ ] L'administrateur peut modifier le template de nommage des fichiers
- [ ] Un aperçu du résultat du template est affiché en temps réel avec un exemple
- [ ] L'administrateur peut ajouter/modifier/supprimer des dossiers racine pour la bibliothèque
- [ ] Les variables disponibles pour le template sont listées et documentées dans l'interface

### US-012.2: Configurer Prowlarr
**En tant que** administrateur,
**je veux** configurer la connexion Prowlarr depuis l'interface,
**afin de** activer la recherche de magazines sur les indexeurs.

**Critères d'acceptation :**
- [ ] L'administrateur peut saisir l'URL et la clé API de Prowlarr
- [ ] Un bouton "Test" vérifie la connexion et affiche le résultat (succès avec version, ou message d'erreur)
- [ ] L'administrateur peut configurer la catégorie par défaut (défaut : 7020)
- [ ] L'administrateur peut configurer l'intervalle de sync RSS

### US-012.3: Gérer les clients de téléchargement
**En tant que** administrateur,
**je veux** ajouter, modifier, tester et supprimer des clients de téléchargement,
**afin de** gérer mes connexions aux logiciels de téléchargement.

**Critères d'acceptation :**
- [ ] L'administrateur peut ajouter un nouveau client en choisissant le type (Deluge, qBittorrent, SABnzbd, NZBGet, Transmission)
- [ ] Les champs de configuration s'adaptent au type de client sélectionné
- [ ] Un bouton "Test" vérifie la connexion
- [ ] L'administrateur peut marquer un client comme actif ou inactif
- [ ] L'administrateur peut supprimer un client (avec confirmation)
- [ ] La suppression est bloquée si des téléchargements sont en cours sur ce client

### US-012.4: Gérer les notifications
**En tant que** administrateur,
**je veux** ajouter, modifier, tester et supprimer des canaux de notification,
**afin de** configurer où et quand je reçois les alertes.

**Critères d'acceptation :**
- [ ] L'administrateur peut ajouter un canal en choisissant le type (Discord, Gotify, Telegram, Webhook)
- [ ] Les champs de configuration s'adaptent au type de canal
- [ ] Un bouton "Test" envoie une notification de test
- [ ] L'administrateur peut activer/désactiver chaque type d'événement par canal
- [ ] L'administrateur peut supprimer un canal (avec confirmation)

### US-012.5: Configurer les métadonnées
**En tant que** administrateur,
**je veux** configurer les sources de métadonnées,
**afin de** activer/désactiver les différents fournisseurs d'information.

**Critères d'acceptation :**
- [ ] L'administrateur peut saisir une clé API Google Books
- [ ] L'administrateur peut activer/désactiver chaque source individuellement (Google Books, ISSN Portal, Internet Archive)
- [ ] Un bouton "Test" vérifie la clé API Google Books
- [ ] L'intervalle de rafraîchissement des métadonnées est configurable

### US-012.6: Configurer les profils de qualité
**En tant que** administrateur,
**je veux** créer et gérer les profils de qualité depuis l'interface,
**afin de** définir mes préférences de téléchargement.

**Critères d'acceptation :**
- [ ] L'administrateur peut créer un nouveau profil, le nommer et ordonner les niveaux de qualité par drag-and-drop
- [ ] Le cutoff est sélectionnable visuellement dans la hiérarchie
- [ ] L'administrateur peut activer/désactiver chaque niveau de qualité
- [ ] L'administrateur peut modifier ou supprimer un profil existant
- [ ] Le nombre de magazines utilisant chaque profil est affiché

### US-012.7: Configurer les paramètres généraux
**En tant que** administrateur,
**je veux** configurer les paramètres généraux de Pressarr,
**afin de** adapter l'application à mon environnement.

**Critères d'acceptation :**
- [ ] L'administrateur peut modifier le port d'écoute (nécessite un redémarrage signalé à l'utilisateur)
- [ ] L'administrateur peut activer/désactiver l'authentification (Forms auth avec mot de passe simple, identique au pattern Sonarr/Radarr)
- [ ] L'administrateur peut configurer le niveau de log (debug, info, warning, error)
- [ ] L'administrateur peut régénérer la clé API
- [ ] L'administrateur peut voir les informations système (version, uptime, espace disque)

## Functional Requirements

### FR-012.1: Navigation par sections
L'interface de configuration DOIT être organisée en sections accessibles via un menu latéral : Médias, Indexeurs, Téléchargement, Notifications, Métadonnées, Qualité, Général.

### FR-012.2: Validation en temps réel
Les formulaires DOIVENT valider les champs en temps réel (URL valide, champs requis, formats acceptés) avant la soumission.

### FR-012.3: Boutons de test
Chaque section nécessitant une connexion externe DOIT avoir un bouton "Test" qui vérifie la connexion et affiche un résultat clair (succès/échec avec détails).

### FR-012.4: Sauvegarde explicite
Les modifications DOIVENT être sauvegardées uniquement quand l'utilisateur clique sur "Sauvegarder". Les modifications non sauvegardées DOIVENT être signalées si l'utilisateur quitte la page.

### FR-012.5: API de configuration
Les paramètres DOIVENT être exposés via l'API /api/v1/config/{section} pour permettre la configuration programmatique.

## Non-Functional Requirements

### NFR-012.1: Réactivité
L'interface de configuration DOIT être réactive et fonctionnelle sur desktop et tablette. Le mode mobile n'est pas obligatoire pour les settings.

### NFR-012.2: Sécurité
Les credentials (mots de passe, clés API, tokens) ne DOIVENT JAMAIS être retournés en clair par l'API après leur première saisie. L'API DOIT retourner un placeholder (ex: "••••••••") pour les champs sensibles.

## Edge Cases & Error Handling

- Si une modification de configuration échoue (validation, permission), un message d'erreur détaillé est affiché sans perdre les modifications saisies.
- Si le test de connexion prend plus de 10 secondes, un timeout est affiché.
- Si le port est changé et qu'il est déjà occupé, une erreur est affichée avant le redémarrage.
- Si l'authentification est activée, l'utilisateur DOIT définir un mot de passe avant de pouvoir sauvegarder.
- Si un dossier racine configuré n'existe pas ou n'est pas accessible, un avertissement est affiché.

## Out of Scope

- Thème clair (dark theme uniquement selon la constitution)
- Configuration multi-utilisateur / rôles
- Import/export de la configuration
- Éditeur YAML brut

## Clarifications

### Session 2026-02-25

- Q: L'authentification est-elle par mot de passe simple (Forms auth) ou multi-méthode ? → A: Forms auth avec mot de passe simple, identique au pattern Sonarr/Radarr.

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Foundation), Feature 005 (Download Clients — config), Feature 009 (Quality Profiles — config), Feature 010 (Notifications — config), Feature 003 (Metadata — config)
- Bloque : Aucune
