# API Contract: Indexer

**Base path**: `/api/v1/indexer`

---

## GET /api/v1/indexer

List all configured indexer connections (Prowlarr).

**Response** `200 OK`: `IndexerConfigResource[]`

```json
[
  {
    "id": 1,
    "name": "Prowlarr",
    "url": "http://192.168.1.100:9696",
    "categories": "7010,7020",
    "enabled": true
  }
]
```

Note: `apiKey` is NEVER returned in responses (NFR-009).

---

## POST /api/v1/indexer

Add an indexer connection.

**Request Body**:

```json
{
  "name": "Prowlarr",
  "url": "http://192.168.1.100:9696",
  "apiKey": "abc123def456",
  "categories": "7010,7020",
  "enabled": true
}
```

**Response** `201 Created`: `IndexerConfigResource`

---

## PUT /api/v1/indexer/{id}

Update an indexer connection.

**Response** `200 OK`: `IndexerConfigResource`

---

## DELETE /api/v1/indexer/{id}

Delete an indexer connection.

**Response** `200 OK`: `{}`

---

## POST /api/v1/indexer/test

Test an indexer connection.

**Request Body**: Same as create.

**Response** `200 OK`:

```json
{
  "isValid": true,
  "message": "Connected to Prowlarr (12 indexers available)"
}
```
