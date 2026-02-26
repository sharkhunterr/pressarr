# Data Model: Pressarr

**Branch**: `001-pressarr` | **Date**: 2026-02-26 | **Plan**: [plan.md](plan.md)

---

## Entity Relationship Overview

```
RootFolder 1──N Magazine N──1 QualityProfile
                  │
                  1
                  │
                  N
                Issue
                  │
                  1
                  │
                  0..1
              IssueFile

DownloadClient (standalone)
Notification (standalone)
IndexerConfig (standalone — Prowlarr connection)
History N──1 Magazine, N──1 Issue (optional)
Blocklist N──1 Magazine, N──1 Issue (optional)
MetadataCache (standalone — provider response cache)
```

---

## Entities

### Magazine

The central entity. Represents a periodical title (e.g., "Science & Vie").

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| title | string(255) | NOT NULL | Display title |
| title_slug | string(255) | NOT NULL, UNIQUE | Normalized title for deduplication and matching |
| issn | string(9) | NULLABLE, UNIQUE when present | International Standard Serial Number (format: XXXX-XXXX) |
| publisher | string(255) | NULLABLE | Publisher name |
| country | string(2) | NULLABLE | ISO 3166-1 alpha-2 country code |
| description | text | NULLABLE | Magazine description |
| frequency | string(20) | NOT NULL, default "monthly" | Publication frequency (see enum below) |
| monitored | boolean | NOT NULL, default true | Whether the system actively searches for issues |
| monitoring_start_date | date | NULLABLE | Issues before this date are "missing", not "wanted" |
| search_terms | string(500) | NULLABLE | Custom search terms (overrides title for Prowlarr queries) |
| cover_path | string(500) | NULLABLE | Relative path to local cover image |
| root_folder_id | integer | FK → RootFolder.id, NOT NULL | Library root folder |
| quality_profile_id | integer | FK → QualityProfile.id, NOT NULL | Quality preferences |
| metadata_provider_id | string(255) | NULLABLE | External ID from the metadata source used at add time |
| metadata_provider | string(50) | NULLABLE | Source name ("google_books", "internet_archive") |
| added_at | datetime | NOT NULL, default now | When the magazine was added to the library |
| last_searched_at | datetime | NULLABLE | Last time an automatic search was performed |
| last_metadata_refresh | datetime | NULLABLE | Last metadata refresh from external sources |

**Indexes**: `title_slug` (unique), `issn` (unique where not null), `root_folder_id`, `quality_profile_id`

**Uniqueness rule** (FR-003): A magazine is unique by `title_slug` + `issn`. If ISSN is null, uniqueness is by `title_slug` alone.

**Frequency enum** (FR-028):
- `weekly` — every 7 days
- `biweekly` — every 14 days
- `monthly` — once per month
- `bimonthly` — every 2 months
- `quarterly` — every 3 months
- `semiannual` — every 6 months
- `annual` — once per year
- `irregular` — no predictable schedule (no forecast generated)

---

### Issue

A specific numbered instance of a magazine (e.g., "N°1285 - Mars 2025").

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| magazine_id | integer | FK → Magazine.id, NOT NULL, ON DELETE CASCADE | Parent magazine |
| number | integer | NULLABLE | Issue number (null for date-only periodicals) |
| volume | integer | NULLABLE | Volume number (if applicable) |
| title | string(255) | NULLABLE | Issue-specific title (e.g., "Spécial Espace") |
| publication_date | date | NULLABLE | Actual or estimated publication date |
| year | integer | NULLABLE | Publication year |
| month | integer | NULLABLE | Publication month (1-12) |
| status | string(20) | NOT NULL, default "missing" | Current status (see state machine below) |
| monitored | boolean | NOT NULL, default true | Whether this specific issue is monitored |
| is_special | boolean | NOT NULL, default false | True for hors-séries |
| is_forecast | boolean | NOT NULL, default false | True for system-generated forecasts |
| cover_path | string(500) | NULLABLE | Relative path to issue cover image |
| added_at | datetime | NOT NULL, default now | When this issue was first known |

**Indexes**: `(magazine_id, number)` (unique where both not null), `(magazine_id, publication_date)`, `status`, `magazine_id`

**Composite uniqueness**: Within a magazine, an issue is unique by `number` (when present) or by `publication_date` (for date-only periodicals).

---

### IssueFile

A physical file on disk associated with an issue (FR-009: at most one active file per issue).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| issue_id | integer | FK → Issue.id, NOT NULL, UNIQUE, ON DELETE CASCADE | Parent issue (1:1) |
| path | string(1000) | NOT NULL | Absolute path to the file |
| relative_path | string(1000) | NOT NULL | Path relative to root folder |
| size | bigint | NOT NULL | File size in bytes |
| format | string(10) | NOT NULL | File format: pdf, epub, cbr, cbz |
| quality | string(20) | NOT NULL, default "unknown" | Detected quality level |
| original_filename | string(500) | NOT NULL | Original filename before renaming |
| release_group | string(100) | NULLABLE | Release group name |
| language | string(5) | NULLABLE | Detected language (ISO 639-1) |
| imported_at | datetime | NOT NULL, default now | When the file was imported |

**Indexes**: `issue_id` (unique — one file per issue), `path` (unique)

**Format enum** (FR-011): `pdf`, `epub`, `cbr`, `cbz`

**Quality enum** (FR-034, ordered lowest to highest):
- `unknown` — quality not determined
- `scan` — scanned pages
- `pdf_lq` — low quality PDF
- `pdf_hq` — high quality PDF
- `retail` — retail/commercial release
- `truepdf` — native/true digital PDF

---

### QualityProfile

Defines acceptable quality levels and upgrade behavior (US-043 to US-047).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| name | string(100) | NOT NULL, UNIQUE | Profile name (e.g., "Default", "Best Quality") |
| cutoff | string(20) | NOT NULL | Quality level at which to stop upgrading |
| is_default | boolean | NOT NULL, default false | Whether this is the system default profile |

---

### QualityProfileItem

Ordered list of allowed quality levels within a profile.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| quality_profile_id | integer | FK → QualityProfile.id, NOT NULL, ON DELETE CASCADE | Parent profile |
| quality | string(20) | NOT NULL | Quality level name |
| allowed | boolean | NOT NULL, default true | Whether this quality is acceptable |
| sort_order | integer | NOT NULL | Position in the hierarchy (higher = better) |

**Indexes**: `(quality_profile_id, quality)` (unique), `(quality_profile_id, sort_order)`

---

### DownloadClient

Configuration for an external download client (US-022).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| name | string(100) | NOT NULL | User-friendly name |
| client_type | string(20) | NOT NULL | Client type: deluge, qbittorrent, transmission, sabnzbd, nzbget |
| protocol | string(10) | NOT NULL | Protocol: torrent, usenet |
| host | string(255) | NOT NULL | Hostname or IP |
| port | integer | NOT NULL | Port number |
| use_ssl | boolean | NOT NULL, default false | Use HTTPS |
| username | string(100) | NULLABLE | Authentication username |
| password | string(255) | NULLABLE | Authentication password (stored encrypted) |
| api_key | string(255) | NULLABLE | API key (for SABnzbd) |
| category | string(50) | NOT NULL, default "pressarr" | Label/category for downloads (Art. II §2.3) |
| is_default | boolean | NOT NULL, default false | Default client for this protocol |
| priority | integer | NOT NULL, default 0 | Priority when multiple clients exist |

**Indexes**: `client_type`, `protocol`

**Constraint**: At most one `is_default=true` per `protocol`.

---

### Notification

Configuration for a notification channel (US-048 to US-052).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| name | string(100) | NOT NULL | User-friendly name |
| notification_type | string(20) | NOT NULL | Channel type: discord, gotify, telegram, webhook |
| settings | text (JSON) | NOT NULL | Channel-specific settings (URL, token, etc.) |
| on_grab | boolean | NOT NULL, default true | Notify on grab events |
| on_download | boolean | NOT NULL, default true | Notify on download completion |
| on_import | boolean | NOT NULL, default true | Notify on successful import |
| on_upgrade | boolean | NOT NULL, default true | Notify on quality upgrade |
| on_error | boolean | NOT NULL, default true | Notify on errors |
| enabled | boolean | NOT NULL, default true | Master toggle |

**Settings JSON structure by type**:
- **discord**: `{"webhookUrl": "..."}`
- **gotify**: `{"serverUrl": "...", "appToken": "...", "priority": 5}`
- **telegram**: `{"botToken": "...", "chatId": "..."}`
- **webhook**: `{"url": "...", "method": "POST", "headers": {"X-Custom": "value"}}`

---

### History

Event log for all significant actions (US-054, FR-041).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| event_type | string(20) | NOT NULL | Event type (see enum) |
| date | datetime | NOT NULL, default now | When the event occurred |
| magazine_id | integer | FK → Magazine.id, NULLABLE, ON DELETE SET NULL | Related magazine |
| issue_id | integer | FK → Issue.id, NULLABLE, ON DELETE SET NULL | Related issue |
| details | text (JSON) | NULLABLE | Event-specific details |

**Indexes**: `date`, `event_type`, `magazine_id`, `(event_type, date)`

**Event types** (FR-041): `grab`, `download`, `import`, `upgrade`, `rename`, `delete`, `error`, `unmatched`

**Retention**: Auto-purged after configurable period (default 365 days, FR-042).

---

### Blocklist

Releases that should never be re-downloaded (US-055, FR-016).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| date | datetime | NOT NULL, default now | When the release was blocklisted |
| magazine_id | integer | FK → Magazine.id, NULLABLE, ON DELETE CASCADE | Related magazine |
| issue_id | integer | FK → Issue.id, NULLABLE, ON DELETE SET NULL | Related issue |
| release_title | string(500) | NOT NULL | Title of the blocklisted release |
| indexer | string(100) | NULLABLE | Indexer name |
| protocol | string(10) | NULLABLE | torrent or usenet |
| reason | string(255) | NULLABLE | Why it was blocklisted |

**Indexes**: `release_title`, `magazine_id`

---

### RootFolder

Library root folder configuration (US-059, FR-045).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| path | string(1000) | NOT NULL, UNIQUE | Absolute path |
| is_default | boolean | NOT NULL, default false | Default folder for new magazines |

**Constraint**: At most one `is_default=true`.

---

### IndexerConfig

Prowlarr connection configuration (US-017).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| name | string(100) | NOT NULL, default "Prowlarr" | Display name |
| url | string(500) | NOT NULL | Prowlarr base URL |
| api_key | string(255) | NOT NULL | Prowlarr API key |
| categories | string(100) | NOT NULL, default "7010,7020" | Search category IDs |
| enabled | boolean | NOT NULL, default true | Whether this indexer connection is active |

---

### MetadataCache

Cache for external metadata provider responses (from research — rreading-glasses pattern).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Internal identifier |
| provider | string(50) | NOT NULL | Provider name ("google_books", "internet_archive") |
| cache_key | string(500) | NOT NULL | Lookup key (e.g., search query, item identifier) |
| response_json | text | NOT NULL | Raw JSON response from the provider |
| fetched_at | datetime | NOT NULL, default now | When the response was cached |
| expires_at | datetime | NOT NULL | When the cache entry becomes stale |

**Indexes**: `(provider, cache_key)` (unique), `expires_at`

---

## State Machine: Issue Status

```
                                     ┌──────────┐
                                     │ upcoming │ (forecast-generated)
                                     └────┬─────┘
                                          │ issue confirmed / import
                                          ▼
┌─────────┐    monitoring ON     ┌─────────┐    search match     ┌──────────┐
│ missing  │ ──────────────────▶ │ wanted  │ ─────────────────▶ │ snatched │
└─────────┘                      └─────────┘                     └────┬─────┘
     ▲                                ▲ │                             │
     │                                │ │ cancel/fail                 │ download
     │ file deleted                   │ ▼                             │ starts
     │                           ┌────────┐                           ▼
     │                           │skipped │                  ┌──────────────┐
     │                           └────────┘                  │ downloading  │
     │                                                       └──────┬───────┘
     │                                                              │
     │                   ┌───────────┐                              │ import
     └───────────────────│ available │◀─────────────────────────────┘
                         └───────────┘
```

**Status definitions** (FR-008):

| Status | Color | Description |
|--------|-------|-------------|
| `available` | Green | File present in library |
| `wanted` | Orange | Monitored, actively searching |
| `missing` | Red | No file, not monitored (before monitoring start date) |
| `downloading` | Blue | Download in progress |
| `snatched` | Purple | Sent to download client, not yet started |
| `upcoming` | Grey | Future forecast, not yet published |
| `skipped` | Grey | User chose to skip this issue |

**Transitions**:

| From | To | Trigger |
|------|-----|---------|
| upcoming | wanted | Date reached + monitored |
| upcoming | missing | Date reached + not monitored |
| missing | wanted | User enables monitoring |
| wanted | snatched | Release grabbed |
| snatched | downloading | Download client reports progress |
| downloading | available | Import pipeline succeeds |
| snatched → wanted | Cancel/fail | Grab fails or is cancelled |
| downloading → wanted | Cancel/fail | Download fails |
| available | missing/wanted | File deleted |
| any | skipped | User skips (manual) |
| skipped | wanted | User un-skips (manual) |

---

## Validation Rules

### Magazine
- `title`: 1-255 characters, trimmed
- `title_slug`: auto-generated from title (lowercase, strip accents, normalize separators)
- `issn`: format `XXXX-XXXX` (validated via check digit) or null
- `frequency`: must be one of the enum values
- `monitoring_start_date`: must be a valid date or null

### Issue
- `number`: positive integer or null
- `volume`: positive integer or null
- `publication_date`: valid date or null
- `status`: must be one of the enum values
- At least one of `number` or `publication_date` must be present

### IssueFile
- `path`: must be an existing file path on disk
- `format`: must be one of: pdf, epub, cbr, cbz
- `quality`: must be one of the quality enum values
- `size`: positive integer

### QualityProfile
- `name`: 1-100 characters, unique
- `cutoff`: must be a valid quality level
- Must have at least one allowed quality item

### DownloadClient
- `host`: valid hostname or IP
- `port`: 1-65535
- `category`: 1-50 characters, default "pressarr"

---

## Computed / Virtual Fields

These fields are not stored but computed in API responses:

### Magazine (API response enrichment)
- `issueCount`: total issues
- `availableCount`: issues with status "available"
- `missingCount`: issues with status "missing" or "wanted"
- `percentComplete`: `availableCount / issueCount * 100`
- `nextIssueDate`: next forecast date (from Issue with is_forecast=true)
- `coverUrl`: URL to serve the cover image

### RootFolder (API response enrichment)
- `freeSpace`: available disk space in bytes (computed at query time)

---

## camelCase API Convention

Per Constitution Art. II §2.1, all API responses use camelCase. The ORM models use snake_case internally (Art. IX §9.1). The Pydantic schemas handle the conversion via `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)`.

Example mapping:
- `magazine_id` → `magazineId`
- `quality_profile_id` → `qualityProfileId`
- `monitoring_start_date` → `monitoringStartDate`
- `is_special` → `isSpecial`
