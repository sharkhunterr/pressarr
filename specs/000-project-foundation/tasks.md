# Tasks: Project Foundation

**Input**: Design documents from `/specs/000-project-foundation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-system.md, quickstart.md

**Tests**: Included — constitution Article III requires tests for API endpoints and critical services.

**Organization**: Tasks grouped by user story in dependency order. US-000.4 (Config) first because it's foundational to all others, then US-000.2 (DB), US-000.3 (Status API), US-000.1 (Frontend + Startup), US-000.5 (Docker).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All paths relative to repository root

---

## Phase 1: Setup (Project Structure)

**Purpose**: Create the directory structure and initialize both backend and frontend projects per plan.md

- [x] T001 Create backend directory structure with all __init__.py files: backend/app/, backend/app/models/, backend/app/schemas/, backend/app/api/, backend/alembic/, backend/alembic/versions/, backend/tests/
- [x] T002 Create backend/pyproject.toml with project metadata (name=pressarr, version=0.1.0, python>=3.12) and dependencies: fastapi, uvicorn[standard], sqlalchemy[asyncio], aiosqlite, alembic, httpx, apscheduler, pyyaml
- [x] T003 Create backend/requirements.txt with pinned dependency versions matching pyproject.toml
- [x] T004 [P] Initialize frontend project: create frontend/package.json, frontend/tsconfig.json, frontend/vite.config.ts with React 18 + TypeScript 5.x + Vite + Tailwind CSS + TanStack Query dependencies

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Implement configuration loader in backend/app/config.py: SystemConfig dataclass with all fields from data-model.md (server_port=8585, server_host="0.0.0.0", api_key, config_dir="/config", magazines_dir="/magazines", downloads_dir="/downloads", log_level="info", db_path), YAML loading with PyYAML, env override with PRESSARR__SECTION__KEY pattern, default values fallback
- [x] T006 [P] Implement logging setup in backend/app/logging.py: Python standard logging module, RotatingFileHandler to {config_dir}/logs/, JSON format for file output, text format for console, configurable level from SystemConfig.log_level
- [x] T007 Implement async database engine and session factory in backend/app/database.py: create_async_engine with aiosqlite, WAL mode pragma, async_sessionmaker, get_session dependency for FastAPI
- [x] T008 [P] Create SQLAlchemy declarative base in backend/app/models/base.py: DeclarativeBase class for all future models
- [x] T009 Setup Alembic configuration: backend/alembic.ini (sqlalchemy.url placeholder), backend/alembic/env.py (async-compatible, imports Base.metadata from models/base.py)
- [x] T010 Create FastAPI application factory with async lifespan in backend/app/main.py: load config, init logging, check /config writable, init database, run migrations, mount API router, mount static files placeholder
- [x] T011 [P] Create API v1 root router in backend/app/api/router.py: APIRouter with prefix="/api/v1"

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 4 — Configuration (Priority: P1) 🎯 MVP

**Goal**: Pressarr reads configuration from YAML + env variables with zero-config first start

**Independent Test**: Start app without any config file → pressarr.yml is auto-created with valid defaults and auto-generated API key. Set PRESSARR__SERVER__PORT=9090 → app listens on port 9090.

### Implementation for User Story 4

- [x] T012 [US4] Implement first-start config write: auto-generate API key (secrets.token_hex(16) = 32 hex chars), write default pressarr.yml to {config_dir}/pressarr.yml in backend/app/config.py
- [x] T013 [US4] Add edge case: /config directory not writable → log clear error message with path + exit code 1 in backend/app/main.py lifespan
- [x] T014 [US4] Add edge case: invalid YAML values → log warning per invalid field + fallback to default value for that field in backend/app/config.py

**Checkpoint**: Configuration system fully functional — app starts with zero config and respects YAML + env overrides

---

## Phase 4: User Story 2 — Auto Database Creation (Priority: P2)

**Goal**: Database is created and migrated automatically at first startup without manual intervention

**Independent Test**: Delete pressarr.db → start app → DB file created at {config_dir}/pressarr.db with alembic_version table. Restart app → existing DB reused, no errors.

### Implementation for User Story 2

- [x] T015 [US2] Create initial Alembic migration (empty schema — only alembic_version table) in backend/alembic/versions/001_initial.py
- [x] T016 [US2] Implement auto-migration on startup: run alembic upgrade head programmatically in backend/app/main.py lifespan after database init
- [x] T017 [US2] Add edge case: corrupted database file → catch OperationalError at startup, log clear error message with db_path + exit code 1 in backend/app/database.py

**Checkpoint**: Database auto-creation and migration work — zero-config DB ready

---

## Phase 5: User Story 3 — Status Endpoint (Priority: P3)

**Goal**: GET /api/v1/system/status returns health and system info compatible with Homepage/Homarr widgets

**Independent Test**: `curl http://localhost:8585/api/v1/system/status` → 200 OK with JSON containing version, uptime, startTime, magazineCount=0, issueCount=0, issueFileCount=0

### Implementation for User Story 3

- [x] T018 [P] [US3] Create SystemStatus Pydantic schema in backend/app/schemas/system.py: version (str), uptime (int, seconds), start_time (datetime ISO 8601), magazine_count (int), issue_count (int), issue_file_count (int). Use alias_generator for camelCase JSON output (startTime, magazineCount, etc.)
- [x] T019 [US3] Implement GET /api/v1/system/status endpoint in backend/app/api/system.py: no authentication required, compute uptime from app start_time stored in app.state, return magazineCount/issueCount/issueFileCount=0 (no tables yet), version from package metadata or constant "0.1.0"
- [x] T020 [US3] Wire system router into API v1 router: import system router in backend/app/api/router.py, include with prefix="/system"

**Checkpoint**: Status API responds correctly — dashboards can query Pressarr health

---

## Phase 6: User Story 1 — Application Startup & Frontend (Priority: P4)

**Goal**: Application starts and displays a dark-themed homepage with "Pressarr" branding and empty library state

**Independent Test**: Start backend + frontend dev servers → navigate to http://localhost:5173 → see dark-themed page with "Pressarr" title and "aucun magazine" empty state message

### Implementation for User Story 1

- [x] T021 [P] [US1] Configure Tailwind CSS dark theme in frontend/tailwind.config.ts: darkMode "class", extend colors with zinc-900/zinc-950 backgrounds, zinc-100 text, accent #E85D04 (press-orange)
- [x] T022 [P] [US1] Create global styles in frontend/src/styles/globals.css: Tailwind directives (@tailwind base/components/utilities), dark body background zinc-950, text zinc-100
- [x] T023 [P] [US1] Create API client fetch wrapper in frontend/src/lib/api.ts: base URL from window.location or env, GET helper with JSON parsing, error handling
- [x] T024 [US1] Create index.html entry point in frontend/index.html: meta viewport, title "Pressarr", dark background, script src main.tsx
- [x] T025 [US1] Create main.tsx entry point in frontend/src/main.tsx: React 18 createRoot, import globals.css, render App
- [x] T026 [US1] Create App.tsx root layout in frontend/src/App.tsx: TanStack QueryClientProvider, React Router with single route "/" → HomePage
- [x] T027 [US1] Create HomePage.tsx in frontend/src/pages/HomePage.tsx: "Pressarr" heading, empty library state message ("Aucun magazine dans la bibliothèque"), dark themed card layout
- [x] T028 [US1] Configure Vite dev proxy in frontend/vite.config.ts: proxy /api/* requests to http://localhost:8585
- [x] T029 [US1] Mount frontend build as static files in backend/app/main.py: serve frontend/dist/ on "/" in production, catch-all route for SPA client-side routing

**Checkpoint**: Full application starts — dark-themed homepage visible with empty library state

---

## Phase 7: User Story 5 — Docker Image (Priority: P5)

**Goal**: Single Docker image produces a fully functional standalone Pressarr instance

**Independent Test**: `docker build -t pressarr:dev .` → `docker run -p 8585:8585 -v ./config:/config pressarr:dev` → browse http://localhost:8585 → see homepage, curl /api/v1/system/status → 200 OK

### Implementation for User Story 5

- [ ] T030 [US5] Create multi-stage Dockerfile: Stage 1 (node:20-alpine) — npm install + npm run build in frontend/. Stage 2 (python:3.12-slim) — pip install from backend/requirements.txt, copy backend/app/, copy frontend build output to static dir, EXPOSE 8585, CMD uvicorn
- [ ] T031 [US5] Create docker-compose.yml: service pressarr with build context, ports 8585:8585, volumes /config, /magazines, /downloads
- [ ] T032 [US5] Add HEALTHCHECK to Dockerfile: curl -f http://localhost:8585/api/v1/system/status every 30s, timeout 10s, retries 3

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Tests, validation, cleanup

- [x] T033 [P] Create test fixtures in backend/tests/conftest.py: async test client (httpx.AsyncClient), in-memory SQLite database, override FastAPI dependencies, app lifespan fixture
- [x] T034 Implement tests for GET /api/v1/system/status in backend/tests/test_system.py: test 200 response, test response contains version field, test response contains uptime >= 0, test response contains magazineCount/issueCount/issueFileCount = 0, test camelCase field names
- [x] T035 [P] Add backend linting config: ruff configuration in backend/pyproject.toml (line-length=120, target Python 3.12, isort), mypy strict mode configuration
- [x] T036 Run quickstart.md validation criteria (backend only — Docker skipped per user request): verify all 7 checkpoints pass (uvicorn starts, DB created, config written, status endpoint works, frontend renders, docker builds, volumes mount)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US4 Config (Phase 3)**: Depends on Foundational (T005 config loader)
- **US2 Auto DB (Phase 4)**: Depends on Foundational (T007 database, T009 alembic)
- **US3 Status (Phase 5)**: Depends on Foundational (T010 app factory, T011 router)
- **US1 Frontend (Phase 6)**: Depends on US3 (backend must serve API) + Foundational
- **US5 Docker (Phase 7)**: Depends on US1 + US3 (full app must work)
- **Polish (Phase 8)**: Depends on US3 minimum (tests target status endpoint)

### User Story Dependencies

- **US4 (Config)**: Can start after Foundational — No dependencies on other stories
- **US2 (Auto DB)**: Can start after Foundational — Independent of US4 (config loader already in foundational)
- **US3 (Status)**: Can start after Foundational — Independent of US2/US4
- **US1 (Frontend)**: Depends on backend being functional (US3 provides the API to verify)
- **US5 (Docker)**: Depends on all other stories being complete

### Within Each User Story

- Models/schemas before services/endpoints
- Core implementation before edge cases
- Backend before frontend (for US1)
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T004 (frontend init) can run in parallel with T001-T003 (backend init)
- **Phase 2**: T006 (logging), T008 (models base), T011 (router) can run in parallel with T005, T007
- **Phase 3-5**: US4, US2, US3 can start in parallel after Foundational (different files, no cross-dependencies)
- **Phase 6**: T021 (tailwind), T022 (globals.css), T023 (api client) can run in parallel
- **Phase 8**: T033 (conftest), T035 (linting) can run in parallel

---

## Parallel Example: Phases 3-5 (after Foundational)

```bash
# These three user stories touch different files and can be worked in parallel:

# US4 - Config (backend/app/config.py, backend/app/main.py edge cases)
Task: "T012 Implement first-start config write in backend/app/config.py"
Task: "T013 Add /config writable check in backend/app/main.py"
Task: "T014 Add invalid YAML fallback in backend/app/config.py"

# US2 - Database (backend/alembic/versions/, backend/app/database.py)
Task: "T015 Create initial Alembic migration in backend/alembic/versions/"
Task: "T016 Implement auto-migration in backend/app/main.py lifespan"
Task: "T017 Add corrupted DB handling in backend/app/database.py"

# US3 - Status (backend/app/schemas/system.py, backend/app/api/system.py)
Task: "T018 Create SystemStatus schema in backend/app/schemas/system.py"
Task: "T019 Implement status endpoint in backend/app/api/system.py"
Task: "T020 Wire system router in backend/app/api/router.py"
```

**Note**: T016 (auto-migration in main.py lifespan) and T013 (/config writable in main.py lifespan) both modify backend/app/main.py — execute T013 before T016 or merge into a single task if implementing simultaneously.

---

## Implementation Strategy

### MVP First (US4 Config + US3 Status)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US4 (Config) — app starts with zero-config
4. Complete Phase 5: US3 (Status) — API responds to health checks
5. **STOP and VALIDATE**: `curl localhost:8585/api/v1/system/status` returns 200

### Incremental Delivery

1. Setup + Foundational → Project skeleton ready
2. + US4 (Config) → App starts, config auto-generated
3. + US2 (Auto DB) → Database created automatically
4. + US3 (Status) → Dashboard widgets can query health
5. + US1 (Frontend) → Visual homepage with dark theme
6. + US5 (Docker) → Deployable container image
7. + Polish → Tests pass, linting clean, quickstart validated

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- All file paths follow plan.md project structure exactly
- Edge cases from spec.md and plan.md are distributed across their relevant user stories
- Constitution Article III compliance: tests included for API endpoint (T033-T034)
- Constitution Article IX: Conventional Commits enforced, ruff configured (T035)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
