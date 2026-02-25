# Research: Project Foundation

**Feature**: 000-project-foundation
**Date**: 2026-02-25

## R-001: Configuration hiérarchique YAML + env

**Decision**: Utiliser PyYAML pour charger /config/pressarr.yml et les variables d'environnement préfixées PRESSARR__ avec double underscore comme séparateur de niveaux.

**Rationale**: Le pattern PRESSARR__SECTION__KEY est standard dans l'écosystème Docker et l'écosystème *arr. PyYAML est la bibliothèque YAML la plus stable et universelle en Python. Le double underscore permet d'adresser les clés imbriquées (ex: PRESSARR__SERVER__PORT=8585 → server.port=8585).

**Alternatives considered**:
- python-dotenv : trop limité pour les configurations imbriquées
- dynaconf : trop complexe pour le besoin (Article V — simplicité)
- Pydantic Settings : possible mais ajouterait une dépendance alors que PyYAML + un petit loader custom suffit
- TOML : moins standard dans l'écosystème *arr que YAML

## R-002: SQLAlchemy async avec SQLite

**Decision**: Utiliser SQLAlchemy 2.0 async avec aiosqlite comme driver, create_async_engine pour le moteur.

**Rationale**: Imposé par la constitution (Article IV — async-first, SQLAlchemy 2.0 style). aiosqlite est le driver async standard pour SQLite avec SQLAlchemy. Le mode WAL est activé pour les performances de lecture concurrente.

**Alternatives considered**:
- SQLAlchemy sync : interdit par la constitution (Article IV)
- Tortoise ORM : non standard, communauté plus petite
- databases (encode) : abandonné en pratique

## R-003: Migrations avec Alembic

**Decision**: Utiliser Alembic avec auto-génération de migrations. Les migrations sont exécutées automatiquement au démarrage de l'application.

**Rationale**: Alembic est le standard de facto pour les migrations SQLAlchemy. L'exécution au démarrage garantit le zero-config (Article VI). Le pattern "run migrations on startup" est utilisé par Sonarr/Radarr (avec Entity Framework) et est adapté à un contexte single-user SQLite.

**Alternatives considered**:
- Migrations manuelles : viole le zero-config (Article VI)
- Pas de framework de migration (CREATE IF NOT EXISTS) : insuffisant pour les évolutions de schéma futures

## R-004: Auto-génération de la clé API

**Decision**: Générer une clé API de 32 caractères hexadécimaux au premier démarrage via le module secrets de Python. La clé est stockée dans le fichier de configuration YAML.

**Rationale**: Le module secrets est la méthode recommandée pour générer des tokens cryptographiquement sûrs en Python. 32 hex = 128 bits d'entropie, suffisant pour une application self-hosted. Stocker dans le YAML permet la persistance sans table DB dédiée (simplicité — Article V).

**Alternatives considered**:
- UUID4 : moins standard pour les API keys
- Stockage en DB : complexité inutile pour un seul token
- Fichier séparé : fragmentation de la config

## R-005: Frontend minimal avec Vite + React

**Decision**: Créer un projet Vite + React + TypeScript avec Tailwind CSS et shadcn/ui. La page d'accueil affiche le nom "Pressarr" et un état vide de bibliothèque.

**Rationale**: Stack imposée par le contexte du projet. Vite est le bundler le plus rapide pour React. shadcn/ui fournit des composants copiés (pas de dépendance runtime), ce qui est idéal pour la personnalisation du dark theme (Article VII). Le frontend est un SPA qui communique uniquement via /api/v1/* (Article I).

**Alternatives considered**:
- Next.js : SSR inutile pour une app self-hosted locale
- Remix : même raison
- Svelte/Vue : non retenu dans le contexte projet

## R-006: Dockerfile multi-stage

**Decision**: Dockerfile multi-stage avec 2 étapes : (1) Node.js pour build le frontend, (2) Python slim pour le backend qui sert les assets statiques.

**Rationale**: Imposé par la constitution (Article VI — image standalone). Le multi-stage minimise la taille de l'image (pas de Node.js en production). Uvicorn sert le backend, FastAPI monte les fichiers statiques du frontend build.

**Alternatives considered**:
- Nginx reverse proxy : complexité inutile pour un seul process (Article V)
- Docker compose multi-container : viole le "standalone image" (Article VI)
- Caddy : inutile quand FastAPI sert les fichiers statiques

## R-007: Logging et rotation

**Decision**: Utiliser le module logging standard Python avec rotation dans /config/logs/. Format JSON pour la lisibilité machine, format texte pour la console.

**Rationale**: Le module logging standard est suffisant (Article V — pas d'over-engineering). La rotation est gérée par RotatingFileHandler. Les logs dans /config/logs/ permettent la persistance via le volume Docker (Article VI).

**Alternatives considered**:
- loguru : dépendance supplémentaire sans bénéfice justifié
- structlog : trop complexe pour le besoin actuel
