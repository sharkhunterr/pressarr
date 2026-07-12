# API Contract: History

**Base path**: `/api/v1/history`

---

## GET /api/v1/history

Get event history (paginated).

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | integer | 1 | Page number |
| pageSize | integer | 20 | Items per page |
| sortKey | string | "date" | Sort field: date, eventType |
| sortDir | string | "desc" | Sort direction: asc, desc |
| eventType | string | — | Filter by event type |
| magazineId | integer | — | Filter by magazine |

**Response** `200 OK`: `PaginatedResource<HistoryResource>`

```json
{
  "page": 1,
  "pageSize": 20,
  "totalRecords": 150,
  "records": [
    {
      "id": 100,
      "eventType": "import",
      "date": "2026-02-26T14:30:00Z",
      "magazineId": 1,
      "magazineTitle": "Science & Vie",
      "issueId": 42,
      "issueNumber": 1285,
      "details": {
        "quality": "truepdf",
        "size": 52428800,
        "releaseGroup": "Team",
        "source": "prowlarr"
      }
    }
  ]
}
```

**Event types**: `grab`, `download`, `import`, `upgrade`, `rename`, `delete`, `error`, `unmatched`

---

## GET /api/v1/history/{id}

Get a single history entry.

**Response** `200 OK`: `HistoryResource`

**Response** `404 Not Found`
