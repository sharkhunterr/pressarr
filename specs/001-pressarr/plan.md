# Implementation Plan: Pressarr

**Branch**: `001-pressarr` | **Date**: 2026-02-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-pressarr/spec.md`

## Summary

Pressarr is an automated magazine collection manager for the *arr ecosystem. It monitors magazine titles, searches for new issues via Prowlarr, downloads them via torrent/usenet clients or Internet Archive, and organizes the library automatically. The unique Calendar Forecast feature predicts future issues based on publication frequency.

The project is a full-stack web application: Python 3.12 backend (FastAPI + SQLAlchemy 2.0 async + SQLite + APScheduler) serving a React 18 frontend (Vite + TypeScript + Tailwind + shadcn/ui). Docker-native, port 8585, zero-config first start.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
  - Backend: FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, HTTPX, APScheduler, aiosqlite, Alembic
  - Frontend: React 18, Vite, Tailwind CSS, shadcn/ui, react-i18next, TanStack Query
**Storage**: SQLite (async via aiosqlite) — `/config/pressarr.db`
**Testing**: pytest + pytest-asyncio (backend), Vitest (frontend)
**Target Platform**: Docker (linux/amd64, linux/arm64)
**Project Type**: Web application (backend API + frontend SPA)
**Performance Goals**: API GET <200ms, list <500ms for 200 items, startup <10s, <256MB RAM idle
**Constraints**: Standalone Docker image, zero-config first start, *arr ecosystem API conventions
**Scale/Scope**: Single user / small group, 200 magazines, 10,000 issues, 73 user stories, 54 FRs, 11 NFRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | Plan Compliance | Status |
|---------|-------------|-----------------|--------|
| I: Architecture Modulaire | backend/ + frontend/ separation, modules per domain, isolated external clients, models/schemas separation | backend/app/{models,schemas,services,api,indexers,download_clients,metadata,notifications,parser,scheduler} — frontend/src/{api,components,pages,hooks,i18n} | PASS |
| II: Compatibilité *arr | /api/v1/{resource}, POST /api/v1/command, camelCase JSON, widget compat, label "pressarr", Prowlarr primary, port 8585, category 7020 | All conventions followed in API contracts | PASS |
| III: Tests d'Abord | 25+ parser tests, mocked HTTP, integration with in-memory SQLite, forecast tests per frequency | Test structure: tests/{unit,integration,contract} — parser 25+ cases, forecast 7 frequencies | PASS |
| IV: Async-First & Type Safety | All I/O async, type hints, Pydantic v2, SQLAlchemy 2.0, HTTPX, Depends() | async throughout, HTTPX for all HTTP, aiosqlite, Pydantic v2 schemas, FastAPI Depends() | PASS |
| V: Simplicité | Direct framework use, one file per concept, no enterprise patterns, max 3 call levels, <50 line functions | route → service → query (3 levels max), one service file per domain | PASS |
| VI: Docker-Native | Standalone image, YAML+env config, /config /magazines /downloads, SQLite in /config, log rotation, zero-config | Dockerfile multi-stage, pressarr.yml + PRESSARR__* env, all paths configurable | PASS |
| VII: UI Sombre | Dark theme, zinc palette, orange accent #E85D04, shadcn/ui, loading/empty/error states, responsive grid, status badge colors | shadcn/ui dark theme, zinc-900/950 bg, orange accent, 4/2/1 column grid, badge colors per constitution | PASS |
| VIII: Résilience | try/except on external calls, graceful degradation, task continuity, retry+backoff, proper HTTP codes, contextual logging | All external clients wrapped, scheduled tasks resilient, structured logging with IDs | PASS |
| IX: Conventions | snake_case/PascalCase/UPPER_CASE, file=concept, /api/v1/ kebab-case singular, Conventional Commits, module docstrings | All naming conventions followed, conventional commits enforced | PASS |
| X: Gouvernance | Constitution primacy, documented deviations | No deviations anticipated | PASS |

**Gate result: ALL PASS** — Proceeding to Phase 0.

### Post-Design Re-evaluation (Phase 1 complete)

| Article | Design Artifact | Compliance Notes | Status |
|---------|----------------|------------------|--------|
| I: Architecture Modulaire | data-model.md: 12 entities with clean separation. contracts/: 15 API files, one per resource | Models ≠ Schemas confirmed. External clients isolated in dedicated directories | PASS |
| II: Compatibilité *arr | contracts/: all follow /api/v1/{resource} singular, POST /api/v1/command for async, camelCase JSON | **Note**: Constitution §2.5 says category 7020, but research found Newznab standard is 7010=Mags, 7020=Ebook. Resolution: search BOTH 7010+7020. Documented in research.md Topic 5. | PASS (with noted deviation) |
| III: Tests d'Abord | quickstart.md: pytest + pytest-asyncio documented. Plan structure: 25+ parser cases, integration with in-memory SQLite | Test commands and dependencies documented in quickstart | PASS |
| IV: Async-First & Type Safety | research.md: aiosqlite + async engine, HTTPX exclusive, Pydantic v2 validation. data-model.md: all fields typed | WAL mode, expire_on_commit=False, PRAGMA foreign_keys=ON documented | PASS |
| V: Simplicité | data-model.md: 12 entities (no over-abstraction). contracts/: straightforward CRUD + command pattern | No enterprise patterns, max 3 call levels maintained | PASS |
| VI: Docker-Native | quickstart.md: Docker setup with /config, /magazines, /downloads. Zero-config first start documented | Auto-migration, auto-API-key, default quality profile on first run | PASS |
| VII: UI Sombre | N/A for Phase 1 (backend-focused design) | Will be verified during frontend implementation. shadcn/ui + dark theme in quickstart | DEFERRED |
| VIII: Résilience | contracts/: proper HTTP codes (201, 404, 409, 422). research.md: retry with backoff, graceful degradation | All external client error handling patterns documented | PASS |
| IX: Conventions | data-model.md: snake_case fields (Python). contracts/: camelCase JSON (API). Routes: /api/v1/{resource} singular | Pydantic alias_generator for camelCase conversion documented | PASS |
| X: Gouvernance | One deviation noted (category 7010+7020 vs 7020 only) | Documented with justification in research.md | PASS |

**Post-design gate result: ALL PASS** (1 noted deviation with justification, 1 deferred to frontend implementation)

## Project Structure

### Documentation (this feature)

```text
specs/001-pressarr/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── api-magazine.md
│   ├── api-issue.md
│   ├── api-search.md
│   ├── api-download.md
│   ├── api-calendar.md
│   ├── api-queue.md
│   ├── api-history.md
│   ├── api-notification.md
│   ├── api-quality.md
│   ├── api-system.md
│   ├── api-command.md
│   ├── api-blocklist.md
│   ├── api-rootfolder.md
│   ├── api-indexer.md
│   └── api-websocket.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory, lifespan, middleware
│   ├── config.py                  # YAML config + PRESSARR__* env override
│   ├── database.py                # SQLAlchemy async engine + session factory
│   ├── dependencies.py            # FastAPI Depends() providers
│   ├── models/                    # SQLAlchemy 2.0 ORM models (Art. I §1.4)
│   │   ├── __init__.py
│   │   ├── magazine.py
│   │   ├── issue.py
│   │   ├── issue_file.py
│   │   ├── quality_profile.py
│   │   ├── download_client.py
│   │   ├── notification.py
│   │   ├── history.py
│   │   ├── blocklist.py
│   │   └── root_folder.py
│   ├── schemas/                   # Pydantic v2 schemas (Art. I §1.4)
│   │   ├── __init__.py
│   │   ├── magazine.py
│   │   ├── issue.py
│   │   ├── quality.py
│   │   ├── download.py
│   │   ├── notification.py
│   │   ├── history.py
│   │   ├── calendar.py
│   │   ├── search.py
│   │   ├── system.py
│   │   └── command.py
│   ├── services/                  # Business logic — one service = one domain (Art. I §1.2)
│   │   ├── __init__.py
│   │   ├── magazine_service.py
│   │   ├── issue_service.py
│   │   ├── search_service.py
│   │   ├── download_service.py
│   │   ├── import_service.py
│   │   ├── calendar_service.py
│   │   ├── notification_service.py
│   │   ├── quality_service.py
│   │   └── history_service.py
│   ├── api/                       # FastAPI routes (Art. II §2.1)
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── magazine.py        # /api/v1/magazine
│   │       ├── issue.py           # /api/v1/issue
│   │       ├── search.py          # /api/v1/search
│   │       ├── download_client.py # /api/v1/downloadclient
│   │       ├── calendar.py        # /api/v1/calendar
│   │       ├── queue.py           # /api/v1/queue
│   │       ├── history.py         # /api/v1/history
│   │       ├── notification.py    # /api/v1/notification
│   │       ├── quality_profile.py # /api/v1/qualityprofile
│   │       ├── root_folder.py     # /api/v1/rootfolder
│   │       ├── system.py          # /api/v1/system
│   │       ├── command.py         # /api/v1/command
│   │       └── websocket.py       # /ws
│   ├── indexers/                  # Indexer clients (Art. I §1.3)
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract indexer interface
│   │   └── prowlarr.py            # Prowlarr API client
│   ├── download_clients/          # Download clients (Art. I §1.3)
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract download client interface
│   │   ├── deluge.py
│   │   ├── qbittorrent.py
│   │   ├── transmission.py
│   │   ├── sabnzbd.py
│   │   ├── nzbget.py
│   │   └── internet_archive.py    # Direct download from IA
│   ├── metadata/                  # Metadata providers (Art. I §1.3)
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract metadata provider interface
│   │   ├── google_books.py
│   │   └── internet_archive.py
│   ├── notifications/             # Notification providers (Art. I §1.3)
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract notification interface
│   │   ├── discord.py
│   │   ├── gotify.py
│   │   ├── telegram.py
│   │   └── webhook.py
│   ├── parser/                    # Filename parser
│   │   ├── __init__.py
│   │   └── magazine_parser.py
│   └── scheduler/                 # APScheduler tasks
│       ├── __init__.py
│       └── tasks.py
├── tests/
│   ├── conftest.py                # Fixtures: async DB, HTTPX mock client
│   ├── unit/
│   │   ├── test_parser.py         # 25+ filename parsing test cases
│   │   ├── test_quality.py        # Quality scoring logic
│   │   └── test_calendar.py       # Forecast for each frequency type
│   ├── integration/
│   │   ├── test_magazine_api.py   # CRUD + search + metadata
│   │   ├── test_issue_api.py      # Issue management + file association
│   │   ├── test_import.py         # Import pipeline end-to-end
│   │   ├── test_search_api.py     # Search + scoring
│   │   └── test_calendar_api.py   # Calendar + forecast
│   └── contract/
│       ├── test_prowlarr.py       # Mocked Prowlarr responses
│       ├── test_download_clients.py
│       └── test_metadata.py       # Mocked Google Books + IA responses
├── alembic/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
├── pyproject.toml
└── requirements.txt

frontend/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── api/                       # API client (Art. I §1.5)
│   │   ├── client.ts              # Base HTTPX-style fetch wrapper with API key
│   │   ├── magazines.ts
│   │   ├── issues.ts
│   │   ├── search.ts
│   │   ├── downloads.ts
│   │   ├── calendar.ts
│   │   ├── queue.ts
│   │   ├── history.ts
│   │   ├── notifications.ts
│   │   ├── quality.ts
│   │   └── system.ts
│   ├── components/
│   │   ├── ui/                    # shadcn/ui components (Art. VII §7.2)
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── PageLayout.tsx
│   │   ├── MagazineCard.tsx
│   │   ├── IssueRow.tsx
│   │   ├── StatusBadge.tsx        # Color-coded per Art. VII §7.5
│   │   ├── CalendarGrid.tsx
│   │   ├── CalendarAgenda.tsx
│   │   ├── QueueItem.tsx
│   │   ├── SearchResult.tsx
│   │   └── CoverImage.tsx
│   ├── pages/
│   │   ├── Library.tsx
│   │   ├── AddMagazine.tsx
│   │   ├── MagazineDetail.tsx
│   │   ├── Calendar.tsx
│   │   ├── Queue.tsx
│   │   ├── History.tsx
│   │   ├── Blocklist.tsx
│   │   └── Settings/
│   │       ├── General.tsx
│   │       ├── DownloadClients.tsx
│   │       ├── Indexers.tsx
│   │       ├── Notifications.tsx
│   │       ├── QualityProfiles.tsx
│   │       ├── NamingTemplate.tsx
│   │       ├── RootFolders.tsx
│   │       ├── Metadata.tsx
│   │       └── System.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   └── useQueue.ts
│   ├── i18n/                      # Internationalization (NFR-011)
│   │   ├── index.ts
│   │   ├── en.json
│   │   └── fr.json
│   └── lib/
│       └── utils.ts
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── index.html

# Root files
Dockerfile                         # Multi-stage: build frontend, serve with backend
docker-compose.yml                 # Dev/prod compose
.dockerignore
```

**Structure Decision**: Web application with backend/frontend separation per Constitution Article I §1.1. Backend follows domain-based module organization (Art. I §1.2) with isolated external clients (Art. I §1.3) and separate models/schemas (Art. I §1.4). Frontend communicates exclusively via API (Art. I §1.5).

## Complexity Tracking

No constitution violations. No complexity justifications needed.
