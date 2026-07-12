# API Contract: Queue

**Base path**: `/api/v1/queue`

---

## GET /api/v1/queue

Get current download queue.

**Response** `200 OK`: `QueueItemResource[]`

```json
[
  {
    "id": 1,
    "magazineId": 1,
    "magazineTitle": "Science & Vie",
    "issueId": 42,
    "issueNumber": 1285,
    "title": "Science.et.Vie.N1285.Mars.2025.FRENCH.TruePDF",
    "status": "downloading",
    "protocol": "torrent",
    "downloadClient": "My qBittorrent",
    "downloadClientId": 1,
    "downloadId": "abc123hash",
    "quality": "truepdf",
    "size": 52428800,
    "sizeLeft": 26214400,
    "progress": 50.0,
    "speed": 1048576,
    "eta": 25,
    "added": "2026-02-26T10:30:00Z",
    "errorMessage": null
  }
]
```

**Status values**: `queued`, `downloading`, `paused`, `postProcessing`, `completed`, `failed`

---

## DELETE /api/v1/queue/{id}

Remove an item from the queue (cancel download).

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| blocklist | boolean | false | Also add the release to the blocklist |

**Response** `200 OK`: `{}`

---

## DELETE /api/v1/queue/bulk

Remove multiple items from the queue.

**Request Body**:

```json
{
  "ids": [1, 2, 3],
  "blocklist": false
}
```

**Response** `200 OK`: `{}`
