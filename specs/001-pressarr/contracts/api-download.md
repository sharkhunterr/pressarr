# API Contract: Download Client

**Base path**: `/api/v1/downloadclient`

---

## GET /api/v1/downloadclient

List all configured download clients.

**Response** `200 OK`: `DownloadClientResource[]`

```json
[
  {
    "id": 1,
    "name": "My qBittorrent",
    "clientType": "qbittorrent",
    "protocol": "torrent",
    "host": "192.168.1.100",
    "port": 8080,
    "useSsl": false,
    "username": "admin",
    "category": "pressarr",
    "isDefault": true,
    "priority": 0
  }
]
```

Note: `password` and `apiKey` are NEVER returned in responses (NFR-009).

---

## GET /api/v1/downloadclient/{id}

Get a single download client.

**Response** `200 OK`: `DownloadClientResource`

**Response** `404 Not Found`

---

## POST /api/v1/downloadclient

Add a download client.

**Request Body**: `DownloadClientCreateResource`

```json
{
  "name": "My qBittorrent",
  "clientType": "qbittorrent",
  "protocol": "torrent",
  "host": "192.168.1.100",
  "port": 8080,
  "useSsl": false,
  "username": "admin",
  "password": "secret",
  "category": "pressarr",
  "isDefault": true
}
```

**Response** `201 Created`: `DownloadClientResource`

**Response** `422 Unprocessable Entity`: Validation errors

---

## PUT /api/v1/downloadclient/{id}

Update a download client.

**Response** `200 OK`: `DownloadClientResource`

---

## DELETE /api/v1/downloadclient/{id}

Delete a download client.

**Response** `200 OK`: `{}`

---

## POST /api/v1/downloadclient/test

Test connection to a download client.

**Request Body**: Same as create (full client config).

**Response** `200 OK`:

```json
{
  "isValid": true,
  "message": "Connection successful"
}
```

**Response** `200 OK` (failure):

```json
{
  "isValid": false,
  "message": "Connection refused: 192.168.1.100:8080"
}
```
