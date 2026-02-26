# API Contract: System

**Base path**: `/api/v1/system`

---

## GET /api/v1/system/status

Get system status (compatible with Homepage/Homarr widgets — FR-051).

**Authentication**: Not required (health check endpoint — FR-044).

**Response** `200 OK`: `SystemStatusResource`

```json
{
  "version": "1.0.0",
  "startTime": "2026-02-26T08:00:00Z",
  "uptime": "2d 6h 30m",
  "magazineCount": 45,
  "issueCount": 2500,
  "availableCount": 1800,
  "missingCount": 700,
  "queueCount": 3,
  "diskSpace": [
    {
      "path": "/magazines",
      "freeSpace": 107374182400,
      "totalSpace": 214748364800
    }
  ]
}
```

---

## GET /api/v1/system/health

Get health check for all connected services.

**Response** `200 OK`: `HealthCheckResource[]`

```json
[
  {
    "source": "prowlarr",
    "type": "indexer",
    "status": "ok",
    "message": "Connected (12 indexers)",
    "lastChecked": "2026-02-26T14:25:00Z"
  },
  {
    "source": "qBittorrent",
    "type": "downloadClient",
    "status": "error",
    "message": "Connection refused: 192.168.1.100:8080",
    "lastChecked": "2026-02-26T14:25:00Z"
  },
  {
    "source": "Google Books",
    "type": "metadata",
    "status": "warning",
    "message": "Quota at 90% (900/1000 requests)",
    "lastChecked": "2026-02-26T14:25:00Z"
  }
]
```

**Status values**: `ok`, `warning`, `error`

---

## GET /api/v1/system/log

Get recent log entries.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| level | string | "info" | Minimum level: debug, info, warning, error |
| page | integer | 1 | Page number |
| pageSize | integer | 50 | Items per page |

**Response** `200 OK`: `PaginatedResource<LogEntryResource>`

```json
{
  "page": 1,
  "pageSize": 50,
  "totalRecords": 500,
  "records": [
    {
      "time": "2026-02-26T14:30:00Z",
      "level": "info",
      "logger": "scheduler.rss_sync",
      "message": "RSS sync completed: 3 new releases found",
      "details": null
    }
  ]
}
```
