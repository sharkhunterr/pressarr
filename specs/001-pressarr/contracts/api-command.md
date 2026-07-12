# API Contract: Command

**Base path**: `/api/v1/command`

Asynchronous command execution following *arr ecosystem conventions (Art. II §2.1).

---

## GET /api/v1/command

List running and recently completed commands.

**Response** `200 OK`: `CommandResource[]`

```json
[
  {
    "id": 1,
    "name": "RssSync",
    "status": "completed",
    "started": "2026-02-26T14:00:00Z",
    "ended": "2026-02-26T14:00:15Z",
    "duration": "00:00:15",
    "message": "RSS sync completed: 3 new releases found",
    "trigger": "scheduled"
  },
  {
    "id": 2,
    "name": "MissingSearch",
    "status": "running",
    "started": "2026-02-26T14:30:00Z",
    "ended": null,
    "duration": null,
    "message": "Searching issue 3 of 12...",
    "trigger": "manual"
  }
]
```

**Status values**: `queued`, `running`, `completed`, `failed`

---

## POST /api/v1/command

Execute an asynchronous command.

### Available Commands

#### RssSync

Trigger RSS sync for all indexers.

```json
{"name": "RssSync"}
```

#### MagazineSearch

Search for all missing/wanted issues of a magazine.

```json
{
  "name": "MagazineSearch",
  "magazineId": 1
}
```

#### IssueSearch

Search for a specific issue.

```json
{
  "name": "IssueSearch",
  "issueId": 42
}
```

#### RefreshMagazine

Refresh metadata for a magazine.

```json
{
  "name": "RefreshMagazine",
  "magazineId": 1
}
```

#### RescanMagazine

Rescan files on disk for a magazine.

```json
{
  "name": "RescanMagazine",
  "magazineId": 1
}
```

#### RenameMagazine

Rename files for a magazine according to template.

```json
{
  "name": "RenameMagazine",
  "magazineId": 1
}
```

#### InternetArchiveSearch

Search Internet Archive for a magazine's missing issues.

```json
{
  "name": "InternetArchiveSearch",
  "magazineId": 1
}
```

#### ForecastRefresh

Regenerate all forecasts.

```json
{"name": "ForecastRefresh"}
```

**Response** `201 Created`: `CommandResource`

---

## GET /api/v1/command/{id}

Get status of a specific command.

**Response** `200 OK`: `CommandResource`
