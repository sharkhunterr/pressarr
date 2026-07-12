# API Contract: WebSocket

**Endpoint**: `/ws`

---

## Connection

WebSocket connection for real-time updates. If authentication is enabled, the API key must be provided as a query parameter: `/ws?apikey={key}`.

---

## Server → Client Messages

All messages are JSON with a `type` field and event-specific payload.

### Queue Update

Sent when download queue changes (every 5 seconds while downloads are active).

```json
{
  "type": "queue",
  "data": [
    {
      "id": 1,
      "magazineTitle": "Science & Vie",
      "issueNumber": 1285,
      "status": "downloading",
      "progress": 75.5,
      "speed": 1048576,
      "eta": 12
    }
  ]
}
```

### Command Status

Sent when an async command changes status.

```json
{
  "type": "command",
  "data": {
    "id": 2,
    "name": "MagazineSearch",
    "status": "completed",
    "message": "Found 3 releases"
  }
}
```

### Issue Status Change

Sent when an issue status changes (import, grab, etc.).

```json
{
  "type": "issue",
  "data": {
    "issueId": 42,
    "magazineId": 1,
    "status": "available",
    "previousStatus": "downloading"
  }
}
```

### Health Check Update

Sent when a service health status changes.

```json
{
  "type": "health",
  "data": {
    "source": "qBittorrent",
    "status": "ok",
    "message": "Connection restored"
  }
}
```
