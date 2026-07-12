# API Contract: Calendar

**Base path**: `/api/v1/calendar`

---

## GET /api/v1/calendar

Get calendar entries (confirmed issues + forecasts) for a date range.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| start | date | first day of current month | Start date (inclusive) |
| end | date | last day of current month | End date (inclusive) |
| includeForecast | boolean | true | Include forecast entries |
| magazineId | integer | — | Filter to a specific magazine |

**Response** `200 OK`: `CalendarEntryResource[]`

```json
[
  {
    "id": 42,
    "magazineId": 1,
    "magazineTitle": "Science & Vie",
    "coverUrl": "/api/v1/magazine/1/cover",
    "number": 1286,
    "publicationDate": "2026-03-15",
    "status": "wanted",
    "isForecast": false,
    "isSpecial": false,
    "hasFile": false
  },
  {
    "id": null,
    "magazineId": 1,
    "magazineTitle": "Science & Vie",
    "coverUrl": "/api/v1/magazine/1/cover",
    "number": 1287,
    "publicationDate": "2026-04-15",
    "status": "upcoming",
    "isForecast": true,
    "isSpecial": false,
    "hasFile": false
  }
]
```

Note: Forecast entries have `id: null` and `isForecast: true`. They are computed from the magazine frequency and last known issue date (FR-027).

---

## POST /api/v1/calendar/{issueId}/skip

Skip a forecast/issue.

**Response** `200 OK`: `IssueResource` with status "skipped"

---

## POST /api/v1/calendar/{issueId}/unskip

Un-skip an issue.

**Response** `200 OK`: `IssueResource` with status reverted to "wanted" or "missing"
