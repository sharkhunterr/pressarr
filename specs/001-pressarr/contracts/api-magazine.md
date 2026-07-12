# API Contract: Magazine

**Base path**: `/api/v1/magazine`

---

## GET /api/v1/magazine

List all magazines.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| sortKey | string | "title" | Sort field: title, added, nextIssue |
| sortDir | string | "asc" | Sort direction: asc, desc |

**Response** `200 OK`: `MagazineResource[]`

```json
[
  {
    "id": 1,
    "title": "Science & Vie",
    "titleSlug": "science-vie",
    "issn": "0036-8369",
    "publisher": "Reworld Media",
    "country": "FR",
    "description": "Magazine de vulgarisation scientifique",
    "frequency": "monthly",
    "monitored": true,
    "monitoringStartDate": "2025-01-01",
    "searchTerms": null,
    "coverUrl": "/api/v1/magazine/1/cover",
    "rootFolderPath": "/magazines",
    "qualityProfileId": 1,
    "added": "2026-02-26T10:00:00Z",
    "statistics": {
      "issueCount": 24,
      "availableCount": 18,
      "missingCount": 4,
      "wantedCount": 2,
      "percentComplete": 75.0
    },
    "nextIssueDate": "2026-03-15"
  }
]
```

---

## GET /api/v1/magazine/{id}

Get a single magazine.

**Response** `200 OK`: `MagazineResource` (same as above)

**Response** `404 Not Found`: `{"message": "Magazine not found"}`

---

## POST /api/v1/magazine

Add a magazine to the library.

**Request Body**: `MagazineCreateResource`

```json
{
  "title": "Science & Vie",
  "issn": "0036-8369",
  "publisher": "Reworld Media",
  "country": "FR",
  "description": "Magazine de vulgarisation scientifique",
  "frequency": "monthly",
  "monitored": true,
  "monitoringStartDate": "2025-01-01",
  "searchTerms": null,
  "rootFolderPath": "/magazines",
  "qualityProfileId": 1,
  "metadataProviderId": "google_books:abc123",
  "searchForMissingIssues": true
}
```

**Response** `201 Created`: `MagazineResource`

**Response** `409 Conflict`: `{"message": "Magazine already exists"}`

**Response** `422 Unprocessable Entity`: Validation errors

---

## PUT /api/v1/magazine/{id}

Update a magazine.

**Request Body**: `MagazineUpdateResource` (partial update, same fields as create)

**Response** `200 OK`: `MagazineResource`

**Response** `404 Not Found`

---

## DELETE /api/v1/magazine/{id}

Delete a magazine.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| deleteFiles | boolean | false | Also delete files from disk |

**Response** `200 OK`: `{}`

**Response** `404 Not Found`

---

## GET /api/v1/magazine/{id}/cover

Serve the magazine cover image.

**Response** `200 OK`: JPEG image (Content-Type: image/jpeg)

**Response** `404 Not Found`: Returns placeholder image

---

## POST /api/v1/magazine/{id}/refresh

Refresh magazine metadata from external sources (triggers async command).

**Response** `200 OK`: `CommandResource` (reference to async command)
