# API Contract: Issue

**Base path**: `/api/v1/issue`

---

## GET /api/v1/issue

List issues (optionally filtered by magazine).

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| magazineId | integer | — | Filter by magazine (required) |
| status | string | — | Filter by status |
| includeForecasts | boolean | true | Include forecast entries |

**Response** `200 OK`: `IssueResource[]`

```json
[
  {
    "id": 42,
    "magazineId": 1,
    "number": 1285,
    "volume": null,
    "title": null,
    "publicationDate": "2025-03-15",
    "year": 2025,
    "month": 3,
    "status": "available",
    "monitored": true,
    "isSpecial": false,
    "isForecast": false,
    "coverUrl": "/api/v1/issue/42/cover",
    "hasFile": true,
    "issueFile": {
      "id": 30,
      "path": "/magazines/Science & Vie/Science & Vie - N1285 (2025-03).pdf",
      "relativePath": "Science & Vie/Science & Vie - N1285 (2025-03).pdf",
      "size": 52428800,
      "format": "pdf",
      "quality": "truepdf",
      "language": "fr",
      "releaseGroup": "Team",
      "importedAt": "2026-02-20T14:30:00Z"
    }
  }
]
```

---

## GET /api/v1/issue/{id}

Get a single issue.

**Response** `200 OK`: `IssueResource`

**Response** `404 Not Found`

---

## PUT /api/v1/issue/{id}

Update an issue (primarily for monitoring toggle).

**Request Body**:

```json
{
  "monitored": false
}
```

**Response** `200 OK`: `IssueResource`

---

## PUT /api/v1/issue/monitor

Batch update monitoring for multiple issues.

**Request Body**:

```json
{
  "issueIds": [42, 43, 44, 45],
  "monitored": true
}
```

**Response** `200 OK`: `IssueResource[]`

---

## DELETE /api/v1/issue/{id}/file

Delete the file associated with an issue.

**Response** `200 OK`: `{}`

**Response** `404 Not Found`

---

## GET /api/v1/issue/{id}/cover

Serve the issue cover image.

**Response** `200 OK`: JPEG image

**Response** `404 Not Found`: Placeholder
