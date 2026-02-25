# Feature 000: Project Foundation

**Branch:** 000-project-foundation
**Date:** 2026-02-25
**Status:** Draft

## Overview

Le socle fondateur de Pressarr : la structure minimale permettant à l'application de démarrer, servir une page web, exposer une API de santé, et persister des données. Cette feature pose les bases sur lesquelles toutes les autres features seront construites.

## User Stories

### US-000.1: Démarrage de l'application
**En tant que** administrateur,
**je veux** que l'application démarre et affiche une page d'accueil,
**afin de** vérifier que l'installation est fonctionnelle.

**Critères d'acceptation :**
- [ ] L'application démarre sans erreur en moins de 30 secondes
- [ ] Une page d'accueil s'affiche dans le navigateur à l'adresse configurée (port 8585 par défaut)
- [ ] La page d'accueil affiche le nom "Pressarr" et un état "aucun magazine" si la bibliothèque est vide
- [ ] La page utilise un thème sombre par défaut

### US-000.2: Création automatique de la base de données
**En tant que** administrateur,
**je veux** que la base de données soit créée automatiquement au premier lancement,
**afin de** ne pas avoir à faire de configuration manuelle.

**Critères d'acceptation :**
- [ ] Au premier démarrage, la base de données est créée dans le dossier de configuration
- [ ] Les migrations sont appliquées automatiquement
- [ ] Une clé API est auto-générée et stockée dans la configuration
- [ ] Les démarrages suivants réutilisent la base existante sans perte de données

### US-000.3: Endpoint de statut système
**En tant que** dashboard externe,
**je veux** interroger un endpoint /api/v1/system/status,
**afin de** afficher l'état de Pressarr dans mon tableau de bord.

**Critères d'acceptation :**
- [ ] L'endpoint GET /api/v1/system/status retourne un code 200
- [ ] La réponse contient le numéro de version de l'application
- [ ] La réponse contient le temps de fonctionnement (uptime)
- [ ] La réponse contient le nombre de magazines dans la bibliothèque

### US-000.4: Configuration par fichier et variables d'environnement
**En tant que** administrateur,
**je veux** configurer Pressarr via un fichier YAML et/ou des variables d'environnement,
**afin de** adapter le comportement à mon infrastructure.

**Critères d'acceptation :**
- [ ] Un fichier de configuration YAML est lu au démarrage depuis /config/pressarr.yml
- [ ] Les variables d'environnement préfixées PRESSARR__* surchargent les valeurs du fichier YAML
- [ ] Si le fichier YAML n'existe pas, l'application démarre avec des valeurs par défaut fonctionnelles
- [ ] Le port d'écoute est configurable (défaut : 8585)
- [ ] Les chemins des dossiers magazines et téléchargements sont configurables

### US-000.5: Image conteneur fonctionnelle
**En tant que** administrateur,
**je veux** déployer Pressarr via une image conteneur unique,
**afin de** simplifier l'installation sur mon serveur.

**Critères d'acceptation :**
- [ ] Une image conteneur produit une application fonctionnelle standalone (backend + interface web)
- [ ] L'image expose le port configuré (8585 par défaut)
- [ ] Les volumes /config, /magazines et /downloads sont montables
- [ ] L'application démarre sans aucune configuration préalable dans le conteneur

## Functional Requirements

### FR-000.1: Serveur API
L'application DOIT exposer une API REST sous le préfixe /api/v1/ et servir l'interface web sur la racine /.

### FR-000.2: Persistance automatique
La base de données DOIT être créée et migrée automatiquement au premier démarrage sans intervention manuelle.

### FR-000.3: Configuration hiérarchique
La configuration DOIT suivre l'ordre de priorité : variables d'environnement > fichier YAML > valeurs par défaut.

### FR-000.4: Auto-génération de la clé API
Au premier démarrage, une clé API DOIT être générée automatiquement et persistée pour les démarrages suivants.

### FR-000.5: Endpoint de santé
L'endpoint /api/v1/system/status DOIT retourner les informations de version, uptime et statistiques de base de la bibliothèque.

## Non-Functional Requirements

### NFR-000.1: Temps de démarrage
L'application DOIT démarrer en moins de 30 secondes sur un matériel raisonnable (NAS grand public).

### NFR-000.2: Zero-config
Le premier démarrage DOIT fonctionner sans aucune configuration préalable.

### NFR-000.3: Compatibilité *arr
L'API DOIT suivre les conventions du pattern /api/v1/{resource} de l'écosystème *arr.

## Edge Cases & Error Handling

- Si le dossier /config n'est pas accessible en écriture, l'application DOIT afficher un message d'erreur clair et ne pas démarrer.
- Si le fichier YAML contient des valeurs invalides, l'application DOIT logger l'erreur et utiliser les valeurs par défaut pour les champs invalides.
- Si la base de données est corrompue, l'application DOIT afficher un message d'erreur clair au démarrage.
- Si le port configuré est déjà occupé, l'application DOIT afficher un message d'erreur explicite.

## Out of Scope

- Authentification utilisateur (Feature 012)
- Interface de configuration dans le navigateur (Feature 012)
- Gestion des magazines (Feature 001)

## Open Questions

Aucune.

## Dependencies

- Dépend de : Aucune (feature fondatrice)
- Bloque : Toutes les autres features (001-013)
