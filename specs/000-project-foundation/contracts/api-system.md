# API Contract: System

**Feature**: 000-project-foundation
**Base path**: /api/v1/system

## GET /api/v1/system/status

Retourne l'état de santé et les informations de base de l'instance Pressarr.

### Request

- **Method**: GET
- **Authentication**: None (endpoint public pour les health checks)
- **Parameters**: None

### Response 200 OK

```json
{
  "version": "0.1.0",
  "uptime": 3600,
  "startTime": "2026-02-25T10:00:00Z",
  "magazineCount": 0,
  "issueCount": 0,
  "issueFileCount": 0
}
```

| Field | Type | Description |
|-------|------|-------------|
| version | string | Numéro de version de Pressarr (semver) |
| uptime | integer | Durée de fonctionnement en secondes |
| startTime | string (ISO 8601) | Date/heure de démarrage |
| magazineCount | integer | Nombre de magazines dans la bibliothèque |
| issueCount | integer | Nombre total d'issues connues |
| issueFileCount | integer | Nombre de fichiers possédés |

### Notes

- Cet endpoint est conçu pour être compatible avec les widgets Homepage, Homarr et Organizr.
- Le format de réponse suit les conventions Sonarr/Radarr pour /api/v1/system/status.
- L'endpoint est accessible sans clé API pour permettre les health checks Docker (HEALTHCHECK).
