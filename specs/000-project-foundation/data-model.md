# Data Model: Project Foundation

**Feature**: 000-project-foundation
**Date**: 2026-02-25

## Entities

### SystemConfig (non-DB, runtime)

Représente la configuration chargée au démarrage. Pas une entité persistée en base — chargée depuis YAML + env.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| server_port | int | 8585 | Port d'écoute HTTP |
| server_host | str | "0.0.0.0" | Adresse d'écoute |
| api_key | str | auto-generated | Clé API (32 hex chars) |
| config_dir | str | "/config" | Dossier de configuration |
| magazines_dir | str | "/magazines" | Dossier bibliothèque |
| downloads_dir | str | "/downloads" | Dossier téléchargements |
| log_level | str | "info" | Niveau de log (debug/info/warning/error) |
| db_path | str | "{config_dir}/pressarr.db" | Chemin de la base SQLite |

### AlembicVersion (DB — gérée par Alembic)

Table automatique de suivi des migrations. Pas modélisée manuellement.

| Field | Type | Description |
|-------|------|-------------|
| version_num | str (PK) | Identifiant de la dernière migration appliquée |

## Notes

- Feature 000 ne crée aucune table métier. Les tables Magazine, Issue, IssueFile seront créées par les features suivantes.
- La base de données est créée vide avec uniquement la table alembic_version.
- Le fichier /config/pressarr.yml est le format de persistance de la configuration. Il est lu au démarrage et écrit au premier lancement (auto-génération API key).

## State Transitions

Aucune pour Feature 000. Les états (wanted, available, missing, etc.) seront définis dans les features suivantes.

## Relationships

Aucune pour Feature 000.
