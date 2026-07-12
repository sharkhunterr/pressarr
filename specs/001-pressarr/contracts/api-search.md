# API Contract: Search

**Base path**: `/api/v1/search`

---

## GET /api/v1/search

Search for releases on indexers (via Prowlarr).

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| issueId | integer | — | Search for a specific issue |
| magazineId | integer | — | Search for all wanted issues of a magazine |
| query | string | — | Free-text search query |

At least one parameter is required.

**Response** `200 OK`: `SearchResultResource[]`

```json
[
  {
    "guid": "prowlarr-unique-id",
    "title": "Science.et.Vie.N1285.Mars.2025.FRENCH.TruePDF",
    "indexer": "NZBgeek",
    "indexerId": 3,
    "size": 52428800,
    "age": 5,
    "publishDate": "2026-02-21T00:00:00Z",
    "protocol": "usenet",
    "seeders": null,
    "leechers": null,
    "quality": "truepdf",
    "language": "fr",
    "score": 95,
    "isBlocklisted": false,
    "downloadUrl": "https://...",
    "infoUrl": "https://...",
    "categories": [{"id": 7010, "name": "Books/Mags"}]
  }
]
```

---

## POST /api/v1/search

Grab a release (send to download client).

**Request Body**: The full `SearchResultResource` object from GET response.

**Response** `200 OK`:

```json
{
  "grabbed": true,
  "downloadClientId": 1,
  "downloadId": "client-assigned-id"
}
```

**Response** `422 Unprocessable Entity`: No download client available

---

## GET /api/v1/search/internetarchive

Search Internet Archive Magazine Rack.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| query | string | — | Search query |
| magazineId | integer | — | Search for issues of a specific magazine |

**Response** `200 OK`: `IASearchResultResource[]`

```json
[
  {
    "identifier": "NationalGeographic-2005-01",
    "title": "National Geographic January 2005",
    "date": "2005-01",
    "publisher": "National Geographic Partners",
    "size": 52428800,
    "formats": ["pdf", "epub", "djvu"],
    "thumbnailUrl": "https://archive.org/services/img/NationalGeographic-2005-01"
  }
]
```

---

## POST /api/v1/search/internetarchive

Download from Internet Archive.

**Request Body**:

```json
{
  "identifier": "NationalGeographic-2005-01",
  "issueId": 42,
  "preferredFormat": "pdf"
}
```

**Response** `200 OK`:

```json
{
  "grabbed": true,
  "downloadId": "ia-download-id"
}
```
