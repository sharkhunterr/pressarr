# API Contract: Blocklist

**Base path**: `/api/v1/blocklist`

---

## GET /api/v1/blocklist

Get blocklisted releases (paginated).

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | integer | 1 | Page number |
| pageSize | integer | 20 | Items per page |
| magazineId | integer | — | Filter by magazine |

**Response** `200 OK`: `PaginatedResource<BlocklistResource>`

```json
{
  "page": 1,
  "pageSize": 20,
  "totalRecords": 5,
  "records": [
    {
      "id": 1,
      "date": "2026-02-25T12:00:00Z",
      "magazineId": 1,
      "magazineTitle": "Science & Vie",
      "issueId": 42,
      "issueNumber": 1285,
      "releaseTitle": "Science.et.Vie.N1285.FRENCH.Scan",
      "indexer": "1337x",
      "protocol": "torrent",
      "reason": "Manual blocklist by user"
    }
  ]
}
```

---

## DELETE /api/v1/blocklist/{id}

Remove a release from the blocklist (unblock).

**Response** `200 OK`: `{}`

---

## DELETE /api/v1/blocklist/bulk

Remove multiple entries from the blocklist.

**Request Body**:

```json
{
  "ids": [1, 2, 3]
}
```

**Response** `200 OK`: `{}`
