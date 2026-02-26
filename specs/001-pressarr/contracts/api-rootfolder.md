# API Contract: Root Folder

**Base path**: `/api/v1/rootfolder`

---

## GET /api/v1/rootfolder

List all root folders with disk space info.

**Response** `200 OK`: `RootFolderResource[]`

```json
[
  {
    "id": 1,
    "path": "/magazines",
    "isDefault": true,
    "freeSpace": 107374182400,
    "totalSpace": 214748364800,
    "magazineCount": 45
  }
]
```

---

## POST /api/v1/rootfolder

Add a root folder.

**Request Body**:

```json
{
  "path": "/magazines-2",
  "isDefault": false
}
```

**Response** `201 Created`: `RootFolderResource`

**Response** `409 Conflict`: Path already exists as root folder

**Response** `422 Unprocessable Entity`: Path does not exist or is not accessible

---

## DELETE /api/v1/rootfolder/{id}

Delete a root folder.

**Response** `200 OK`: `{}`

**Response** `409 Conflict`: `{"message": "Root folder is in use by N magazines"}`
