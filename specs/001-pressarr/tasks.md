# Tasks: Pressarr — Automated Magazine Collection Manager

**Input**: Design documents from `/specs/001-pressarr/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md
**Tests**: Included per Constitution Article III (parser 25+ cases, integration with in-memory SQLite, mocked HTTP contracts, forecast per frequency)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US066, US001)
- All file paths are relative to repository root

---

## Phase 1: Project Setup

**Purpose**: Create project directory structure and initialize both projects

- [ ] T001 Create project directory structure per plan.md: backend/app/{models,schemas,services,api/v1,indexers,download_clients,metadata,notifications,parser,scheduler}, backend/tests/{unit,integration,contract}, frontend/src/{api,components/ui,components/layout,pages/Settings,hooks,i18n,lib}
- [ ] T002 [P] Initialize Python backend project with pyproject.toml, requirements.txt (per quickstart.md), and all __init__.py files in backend/
- [ ] T003 [P] Initialize frontend with Vite + React + TypeScript (`npm create vite@latest . -- --template react-ts`) in frontend/
- [ ] T004 [P] Create .gitignore (Python + Node) and .dockerignore files at repository root
- [ ] T005 [P] Create docker-compose.yml for development (backend + frontend services, volume mounts) at repository root

**Checkpoint**: Both projects initialize and run without errors (empty app)

---

## Phase 2: Backend Foundation

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Implement config system (YAML /config/pressarr.yml + env vars PRESSARR__* override, nested double-underscore separator) in backend/app/config.py
- [ ] T007 [P] Implement async database engine + session factory (create_async_engine with aiosqlite, WAL mode, PRAGMA foreign_keys=ON, busy_timeout=5000, expire_on_commit=False) in backend/app/database.py
- [ ] T008 Implement FastAPI app factory with lifespan (auto-migration via Alembic on startup, structured logging setup) in backend/app/main.py
- [ ] T009 [P] Implement auth middleware (optional X-Api-Key header, exempt /api/v1/system/status and /api/docs, auto-generate key on first start and log it) in backend/app/main.py
- [ ] T010 [P] Implement FastAPI Depends() providers (get_db yielding AsyncSession with commit/rollback, get_config) in backend/app/dependencies.py
- [ ] T011 [P] Create base Pydantic schema config with camelCase alias_generator (ConfigDict with alias_generator=to_camel, populate_by_name=True) and PaginatedResource generic in backend/app/schemas/__init__.py
- [ ] T012 Create all ORM model files per data-model.md specification in backend/app/models/: magazine.py (Magazine), issue.py (Issue), issue_file.py (IssueFile), quality_profile.py (QualityProfile + QualityProfileItem), download_client.py (DownloadClient), notification.py (Notification), history.py (History), blocklist.py (Blocklist), root_folder.py (RootFolder), indexer_config.py (IndexerConfig), metadata_cache.py (MetadataCache). Use Mapped[] annotations, all relationships, indexes, and constraints as specified.
- [ ] T013 Initialize Alembic async setup (`alembic init -t async`) and create initial migration containing all models in backend/alembic/
- [ ] T014 [P] Create command Pydantic schemas (CommandResource with name, status, started, ended, message, trigger) and implement command_service.py (async command execution framework, command registry, status tracking via in-memory dict) in backend/app/schemas/command.py + backend/app/services/command_service.py
- [ ] T015 [P] Implement /api/v1/command routes (GET list, POST execute, GET by id) per api-command.md contract in backend/app/api/v1/command.py
- [ ] T016 [P] Setup APScheduler AsyncIOScheduler (in-memory job store, replace_existing=True, start in lifespan, shutdown on app stop) in backend/app/scheduler/__init__.py
- [ ] T017 [P] Implement WebSocket connection manager (accept connections, broadcast by message type, handle /ws?apikey= auth, manage connection lifecycle) in backend/app/api/v1/websocket.py
- [ ] T018 Create test infrastructure (conftest.py with async in-memory SQLite using StaticPool, AsyncClient fixture via httpx, test database with auto-migration, fixture for test config) in backend/tests/conftest.py

**Checkpoint**: `uvicorn app.main:app --reload` starts successfully, /api/docs shows Swagger UI, database is created with all tables, command API responds

---

## Phase 3: Frontend Foundation

**Purpose**: Base frontend infrastructure with routing, theming, and shared components

- [ ] T019 Configure Vite with API proxy (/api → localhost:8585, /ws → ws://localhost:8585) in frontend/vite.config.ts
- [ ] T020 [P] Configure Tailwind CSS dark theme (zinc-900/zinc-950 backgrounds, zinc-100 text, orange accent #E85D04) in frontend/tailwind.config.ts
- [ ] T021 [P] Install and configure shadcn/ui (`npx shadcn@latest init`, install: button, card, input, select, badge, dialog, dropdown-menu, table, toast, tabs, separator, skeleton)
- [ ] T022 [P] Setup react-router-dom with all route definitions (/, /add, /magazine/:id, /calendar, /queue, /history, /blocklist, /settings/*) in frontend/src/App.tsx
- [ ] T023 [P] Setup react-i18next with initial en.json and fr.json (navigation labels, common actions, status names) in frontend/src/i18n/
- [ ] T024 [P] Setup TanStack Query provider (QueryClient with staleTime 30s, retry 1) in frontend/src/main.tsx
- [ ] T025 Create base API client (fetch wrapper with X-Api-Key header from localStorage, base URL /api/v1, JSON parsing, error handling) in frontend/src/api/client.ts
- [ ] T026 [P] Create layout components: Sidebar (nav links with icons, active state, Pressarr logo), Header (page title, breadcrumb), PageLayout (sidebar + header + content area) in frontend/src/components/layout/
- [ ] T027 [P] Create StatusBadge component (green=available, orange=wanted, red=missing, blue=downloading, purple=snatched, grey=upcoming/skipped, per Art. VII §7.5) in frontend/src/components/StatusBadge.tsx
- [ ] T028 [P] Create CoverImage component (3:4 aspect ratio, lazy loading, placeholder with magazine title when no cover) in frontend/src/components/CoverImage.tsx
- [ ] T029 [P] Create useWebSocket hook (connect to /ws, auto-reconnect, parse JSON messages by type, expose typed event handlers) in frontend/src/hooks/useWebSocket.ts

**Checkpoint**: Frontend dev server starts at localhost:5173, dark theme renders, navigation works, all routes show placeholder pages

---

## Phase 4: Parser (US-066 to US-069) 🎯 MVP Foundation

**Goal**: Reliable filename parser that extracts structured info from magazine filenames with 25+ test cases

**Independent Test**: `pytest tests/unit/test_parser.py -v` passes all 25+ cases

- [ ] T030 [P] [US069] Write 25+ parser unit tests covering: multi-separator formats (dots, spaces, underscores, tirets), multilingual months (FR/EN/DE/ES/IT), issue numbers (N1285, Issue 12, #42), volumes, quality tags (TruePDF, Retail, Scan, HQ, LQ), language tags (FRENCH, ENGLISH, etc.), hors-série markers (HS, Hors-Serie, Special), format detection (PDF, EPUB, CBR, CBZ), release groups, date-only periodicals, edge cases (double issues, no number) in backend/tests/unit/test_parser.py
- [ ] T031 [US066] Implement magazine filename parser: normalize separators → extract format extension → extract quality/language/release group tokens → extract issue number/volume → extract date (month+year) → remaining tokens = title. Return ParseResult dataclass with all fields (unknown for missing) in backend/app/parser/magazine_parser.py
- [ ] T032 [US067] Add multilingual month name lookup tables (janvier-décembre, january-december, januar-dezember, enero-diciembre, gennaio-dicembre) and quality keyword mapping (truepdf→truepdf, retail→retail, scan→scan, hq→pdf_hq, lq→pdf_lq) in backend/app/parser/magazine_parser.py
- [ ] T033 [US068] Implement fuzzy title matching function using rapidfuzz: normalize_title (lowercase, strip accents, remove articles le/la/les/the/a/an, collapse separators), WRatio scorer, 80% threshold, return (best_match, score) or None in backend/app/parser/magazine_parser.py
- [ ] T034 [US069] Run all parser tests and verify 25+ cases pass

**Checkpoint**: Parser correctly handles `Science.et.Vie.N1285.Mars.2025.FRENCH.TruePDF.pdf`, `National Geographic - 2025-03 (March).pdf`, `Hors-Serie.Science.et.Vie.HS42.2025.pdf` and 22+ more patterns

---

## Phase 5: Quality Profiles (US-043 to US-047)

**Goal**: Quality hierarchy with profiles, cutoff, and upgrade logic

**Independent Test**: `pytest tests/unit/test_quality.py -v` passes; GET/POST/PUT/DELETE /api/v1/qualityprofile work correctly

- [ ] T035 [P] [US043] Write quality unit tests (hierarchy ordering: unknown < scan < pdf_lq < pdf_hq < retail < truepdf, cutoff comparison, upgrade eligibility: current < cutoff AND new > current, profile with only some qualities allowed) in backend/tests/unit/test_quality.py
- [ ] T036 [P] [US043] Create quality Pydantic schemas (QualityProfileResource, QualityProfileItemResource, QualityProfileCreateResource) in backend/app/schemas/quality.py
- [ ] T037 [US043] Implement quality_service.py: CRUD operations, compare_quality(a, b) → int, is_at_cutoff(quality, profile) → bool, should_upgrade(current_quality, new_quality, profile) → bool, validate profile (at least one allowed quality) in backend/app/services/quality_service.py
- [ ] T038 [US043] Implement /api/v1/qualityprofile routes (GET list, GET by id, POST create, PUT update, DELETE with 409 if in use by magazines) per api-quality.md contract in backend/app/api/v1/quality_profile.py
- [ ] T039 [US043] Add default quality profile auto-creation ("Default" — all qualities allowed, cutoff at pdf_hq) on first start in app lifespan in backend/app/main.py
- [ ] T040 [P] [US043] Create quality API client (getProfiles, getProfile, createProfile, updateProfile, deleteProfile) in frontend/src/api/quality.ts
- [ ] T041 [US043] Create QualityProfiles settings page (list profiles, create/edit modal with drag-reorder items, cutoff selector, delete with protection message) in frontend/src/pages/Settings/QualityProfiles.tsx

**Checkpoint**: Default quality profile exists after first start. CRUD operations work. Cutoff logic correctly determines upgrade eligibility.

---

## Phase 6: Magazine Management (US-001 to US-008)

**Goal**: Full magazine CRUD with metadata search from Google Books and Internet Archive

**Independent Test**: `pytest tests/integration/test_magazine_api.py tests/contract/test_metadata.py -v` passes; Library page shows magazines in grid

- [ ] T042 [P] [US001] Write magazine API integration tests (create, read, update, delete, uniqueness by title_slug+ISSN, computed statistics, cover endpoint, 409 on duplicate) in backend/tests/integration/test_magazine_api.py
- [ ] T043 [P] [US001] Write contract tests for metadata providers (mocked Google Books response with printType=magazines, mocked IA scrape API response, deduplication across sources) in backend/tests/contract/test_metadata.py
- [ ] T044 [P] [US001] Create magazine Pydantic schemas (MagazineResource with nested statistics object, MagazineCreateResource with searchForMissingIssues flag, MagazineUpdateResource) per api-magazine.md contract in backend/app/schemas/magazine.py
- [ ] T045 [US002] Implement magazine_service.py: CRUD operations, title_slug generation (lowercase, strip accents, normalize separators), uniqueness check (title_slug + ISSN), computed stats (issueCount, availableCount, missingCount, percentComplete), cover serving from disk, search metadata across providers, populate issues from metadata results in backend/app/services/magazine_service.py
- [ ] T046 [US001] Implement /api/v1/magazine routes (GET list with sortKey/sortDir, GET by id, POST create with 409 duplicate check, PUT update, DELETE with deleteFiles param, GET cover, POST refresh triggering RefreshMagazine command) per api-magazine.md contract in backend/app/api/v1/magazine.py
- [ ] T047 [US059] Implement /api/v1/rootfolder routes (GET with computed freeSpace/totalSpace via shutil.disk_usage, POST with path existence validation and 409 duplicate/422 invalid, DELETE with 409 if in use) per api-rootfolder.md contract in backend/app/api/v1/root_folder.py
- [ ] T048 [P] [US001] Implement metadata provider abstract base class (async search(query) → list[MetadataResult], async get_issues(provider_id) → list[IssueMetadata]) in backend/app/metadata/base.py
- [ ] T049 [P] [US001] Implement Google Books metadata provider (HTTPX GET to googleapis.com/books/v1/volumes?q={query}&printType=magazines, parse volume items, extract title/publisher/description/cover, read-through cache in MetadataCache table, TTL 24h) in backend/app/metadata/google_books.py
- [ ] T050 [P] [US001] Implement Internet Archive metadata provider (HTTPX GET to archive.org/advancedsearch.php with collection:magazinerack, parse response docs, get item metadata via archive.org/metadata/{id}, rate limit 1 req/sec via asyncio.Semaphore, cache results) in backend/app/metadata/internet_archive.py
- [ ] T051 [P] [US003] Create magazines API client (getMagazines, getMagazine, createMagazine, updateMagazine, deleteMagazine, searchMetadata, refreshMetadata) in frontend/src/api/magazines.ts
- [ ] T052 [P] [US003] Create MagazineCard component (CoverImage, title, completion bar, status badge, click navigates to detail) in frontend/src/components/MagazineCard.tsx
- [ ] T053 [US003] Create Library page (responsive grid 4/2/1 columns, sort dropdown title/added/nextIssue, filter by monitored/completeness, empty state with "Add Magazine" CTA, loading skeletons) in frontend/src/pages/Library.tsx
- [ ] T054 [US001] Create AddMagazine page (search input with debounce, metadata results list with "already in library" indicator, manual add form with title/frequency/rootFolder/qualityProfile/monitoringStartDate, searchForMissingIssues toggle) in frontend/src/pages/AddMagazine.tsx
- [ ] T055 [US004] Create MagazineDetail page (cover + metadata header, edit modal for parameters, delete with confirmation dialog and deleteFiles checkbox, refresh button, statistics overview) in frontend/src/pages/MagazineDetail.tsx

**Checkpoint**: User can search for a magazine, add it to library, see it in the grid, view its detail page, edit parameters, delete it. Metadata comes from Google Books or Internet Archive.

---

## Phase 7: Issue & File Management (US-009 to US-016)

**Goal**: Issue listing, monitoring, file operations, folder scanning, and PDF cover extraction

**Independent Test**: `pytest tests/integration/test_issue_api.py -v` passes; Issues display in MagazineDetail grouped by year

- [ ] T056 [P] [US009] Write issue API integration tests (list by magazine, status display, batch monitoring, file association, cover serving) in backend/tests/integration/test_issue_api.py
- [ ] T057 [P] [US009] Create issue Pydantic schemas (IssueResource with nested optional IssueFileResource, IssueBatchMonitorRequest with issueIds + monitored) per api-issue.md contract in backend/app/schemas/issue.py
- [ ] T058 [US009] Implement issue_service.py: list by magazine (grouped by year via query), status management per state machine (data-model.md transitions), toggle monitoring (single + batch), file association/deletion, folder scan (parse filenames → match known issues → report unmatched), rename command (preview + execute per naming template) in backend/app/services/issue_service.py
- [ ] T059 [US009] Implement /api/v1/issue routes (GET list with magazineId filter, GET by id with nested file, PUT update monitored, PUT /monitor for batch, DELETE /{id}/file, GET /{id}/cover) per api-issue.md contract in backend/app/api/v1/issue.py
- [ ] T060 [US030] Implement PDF cover extraction (PyMuPDF: open PDF → get page 0 → render to pixmap → convert to JPEG → resize to max 500px wide → save to /config/covers/, run_in_executor for async, placeholder on failure) in backend/app/services/import_service.py
- [ ] T061 [P] [US009] Create issues API client (getIssues, getIssue, updateIssue, batchMonitor, deleteFile, getCover) in frontend/src/api/issues.ts
- [ ] T062 [US009] Create IssueRow component (number, date, StatusBadge, file info when available: size/format/quality, action buttons: search/monitor toggle/delete file) in frontend/src/components/IssueRow.tsx
- [ ] T063 [US009] Add issue list to MagazineDetail page (grouped by year headers, status filters, hors-séries visually distinguished, loading skeletons) in frontend/src/pages/MagazineDetail.tsx
- [ ] T064 [US010] Add batch monitoring UI (checkbox selection, "Monitor All"/"Unmonitor All" buttons, selection count) to MagazineDetail page
- [ ] T065 [US012] Implement RescanMagazine command handler (scan magazine folder recursively, parse each file with magazine_parser, match against known issues, create IssueFile records, report stats) in backend/app/services/issue_service.py
- [ ] T066 [US013] Implement RenameMagazine command handler (generate preview of old→new filenames per naming template, execute rename+move when confirmed) in backend/app/services/issue_service.py

**Checkpoint**: Issues display correctly in MagazineDetail. Batch monitoring works. Folder scan detects existing files. PDF covers are extracted.

---

## Phase 8: Configuration (US-017, US-022, US-032, US-058 to US-065)

**Goal**: All settings pages — indexers, download clients, naming template, root folders, metadata, general, system health

**Independent Test**: `pytest tests/contract/test_prowlarr.py tests/contract/test_download_clients.py -v` passes; all Settings pages render and submit forms

### Backend: Indexers & Download Clients

- [ ] T067 [P] [US017] Create indexer + download client Pydantic schemas (IndexerConfigResource without apiKey in response, DownloadClientResource without password/apiKey in response, TestResult with isValid + message) in backend/app/schemas/download.py
- [ ] T068 [P] [US017] Implement abstract indexer base (async search(query, categories) → list[RawResult], async rss_feed(categories) → list[RawResult], async test_connection() → TestResult) in backend/app/indexers/base.py
- [ ] T069 [US017] Implement Prowlarr API client (HTTPX calls to {url}/api/v1/search + /api/v1/indexer, X-Api-Key header, categories 7010+7020, parse Newznab results, handle connection errors gracefully) in backend/app/indexers/prowlarr.py
- [ ] T070 [P] [US017] Write Prowlarr contract tests (mocked search response, RSS response, connection test success/failure) in backend/tests/contract/test_prowlarr.py
- [ ] T071 [US017] Implement /api/v1/indexer routes (GET list, POST create, PUT update, DELETE, POST /test — apiKey NEVER in GET responses per NFR-009) per api-indexer.md contract in backend/app/api/v1/indexer.py
- [ ] T072 [P] [US022] Implement abstract download client base (async add_torrent/add_nzb, async get_status(download_id) → DownloadStatus, async remove(download_id), async test_connection() → TestResult) in backend/app/download_clients/base.py
- [ ] T073 [P] [US022] Implement Deluge client (JSON-RPC via HTTPX, auth.login → core.add_torrent_url with label plugin, core.get_torrent_status) in backend/app/download_clients/deluge.py
- [ ] T074 [P] [US022] Implement qBittorrent client (REST /api/v2 via HTTPX, /auth/login cookie, /torrents/add with category, /torrents/info) in backend/app/download_clients/qbittorrent.py
- [ ] T075 [P] [US022] Implement Transmission client (JSON-RPC via HTTPX, 409 X-Transmission-Session-Id challenge, torrent-add with download-dir, torrent-get) in backend/app/download_clients/transmission.py
- [ ] T076 [P] [US022] Implement SABnzbd client (REST with apikey query param via HTTPX, mode=addurl with cat=pressarr, mode=queue for status) in backend/app/download_clients/sabnzbd.py
- [ ] T077 [P] [US022] Implement NZBGet client (JSON-RPC via HTTPX with HTTP Basic auth, append method with Category=pressarr, listgroups for status) in backend/app/download_clients/nzbget.py
- [ ] T078 [P] [US022] Write download client contract tests (mocked responses for each client type: add, status, remove, test connection) in backend/tests/contract/test_download_clients.py
- [ ] T079 [US022] Implement /api/v1/downloadclient routes (GET list, POST create, PUT update, DELETE, POST /test — password/apiKey NEVER in GET responses) per api-download.md contract in backend/app/api/v1/download_client.py

### Backend: System & Config

- [ ] T080 [US032] Implement naming template system: parse template variables ({titre_magazine}, {numero}, {volume}, {annee}, {mois}, {qualite}, {format}, {groupe}), validate template (no filesystem-invalid chars), apply to ParseResult → filename, provide default template, preview function in backend/app/services/import_service.py
- [ ] T081 [P] [US065] Create system Pydantic schemas (SystemStatusResource, HealthCheckResource, LogEntryResource) in backend/app/schemas/system.py
- [ ] T082 [US065] Implement /api/v1/system routes (GET /status with version/uptime/counts/diskSpace — no auth required, GET /health checking all connections, GET /log paginated) per api-system.md contract in backend/app/api/v1/system.py

### Frontend: Settings Pages

- [ ] T083 [P] [US022] Create downloads API client (getClients, createClient, updateClient, deleteClient, testClient, getIndexers, createIndexer, updateIndexer, deleteIndexer, testIndexer) in frontend/src/api/downloads.ts
- [ ] T084 [P] [US065] Create system API client (getStatus, getHealth, getLogs) in frontend/src/api/system.ts
- [ ] T085 [US017] Create Indexers settings page (list indexers, add/edit dialog with URL + API key + categories, test button with success/error feedback) in frontend/src/pages/Settings/Indexers.tsx
- [ ] T086 [US022] Create DownloadClients settings page (list clients, add/edit dialog with type selector + connection fields, test button, default toggle per protocol) in frontend/src/pages/Settings/DownloadClients.tsx
- [ ] T087 [US059] Create RootFolders settings page (list folders with free/total space bars, add dialog with path input, delete with in-use protection) in frontend/src/pages/Settings/RootFolders.tsx
- [ ] T088 [US032] Create NamingTemplate settings page (template input, variable reference list, live preview with sample data, save button) in frontend/src/pages/Settings/NamingTemplate.tsx
- [ ] T089 [US060] Create Metadata settings page (Google Books API key input + test, Internet Archive toggle, test buttons per source) in frontend/src/pages/Settings/Metadata.tsx
- [ ] T090 [US061] Create General settings page (port display + restart warning, log level dropdown, auth toggle, scheduled task intervals) in frontend/src/pages/Settings/General.tsx
- [ ] T091 [US065] Create System page (version, uptime, connection health indicators with green/red dots, global stats, disk space) in frontend/src/pages/Settings/System.tsx

**Checkpoint**: All settings pages functional. Prowlarr test connection works. Download clients can be added and tested. System health page shows connection status.

---

## Phase 9: Search & Download (US-018 to US-021, US-026)

**Goal**: Search indexers via Prowlarr, score results, grab releases to download clients

**Independent Test**: `pytest tests/integration/test_search_api.py -v` passes; manual search from MagazineDetail returns scored results

- [ ] T092 [P] [US018] Create search Pydantic schemas (SearchResultResource with guid/title/indexer/size/age/protocol/seeders/quality/language/score/isBlocklisted, GrabResponse) per api-search.md contract in backend/app/schemas/search.py
- [ ] T093 [US026] Implement search_service.py: build Prowlarr query from issue/magazine, parse results through magazine_parser for quality/language detection, score releases (title match weight + quality vs profile weight + size preference + seeds/age bonus + language bonus), filter blocklisted, sort by score descending in backend/app/services/search_service.py
- [ ] T094 [US018] Implement /api/v1/search routes (GET with issueId/magazineId/query params, POST grab sending release to download client) per api-search.md contract in backend/app/api/v1/search.py
- [ ] T095 [US021] Implement download_service.py: select download client by protocol (torrent/usenet), send release via client.add_torrent/add_nzb with category "pressarr", update issue status to "snatched", create history event "grab", handle client unavailable with explicit error in backend/app/services/download_service.py
- [ ] T096 [P] [US018] Write search API integration tests (search returns scored results, grab updates issue status, blocklist filtering, quality filtering) in backend/tests/integration/test_search_api.py
- [ ] T097 [P] [US018] Create search API client (searchIssue, searchMagazine, freeSearch, grabRelease) in frontend/src/api/search.ts
- [ ] T098 [US018] Create SearchResult component (title, quality badge, size formatted, seeds/age, indexer name, score bar, grab button, blocklist indicator) in frontend/src/components/SearchResult.tsx
- [ ] T099 [US018] Add manual search modal to MagazineDetail page (trigger from issue row or magazine-level "Search Missing" button, display SearchResult list, grab action updates issue status) in frontend/src/pages/MagazineDetail.tsx

**Checkpoint**: User can search for an issue, see scored results, grab a release. Release is sent to the configured download client. Issue status changes to "snatched".

---

## Phase 10: Import Pipeline (US-025, US-027 to US-031)

**Goal**: Complete automated import chain: detect → parse → match → rename → move → update DB → extract cover → notify

**Independent Test**: `pytest tests/integration/test_import.py -v` passes; a file placed in the download directory is automatically imported

- [ ] T100 [P] [US027] Write import pipeline integration tests (parse filename → match issue → rename per template → move to library folder → update DB status to available → cover extraction → history event created) in backend/tests/integration/test_import.py
- [ ] T101 [US027] Implement full import pipeline in import_service.py: detect completed file → parse filename with magazine_parser → fuzzy match title to known magazine → match issue by number/date → check quality vs profile (upgrade if better) → apply naming template → create destination directory → move file (aiofiles/shutil) → create IssueFile record → update issue status to "available" → extract PDF cover → dispatch notifications → create history event "import". Handle errors: unmatched → move to /downloads/unmatched + history "unmatched", disk full → keep in download dir + history "error" in backend/app/services/import_service.py
- [ ] T102 [US029] Integrate naming template into import pipeline (load template from config, apply variables from ParseResult, sanitize filename, handle missing variables gracefully) in backend/app/services/import_service.py
- [ ] T103 [US028] Integrate fuzzy matching into import pipeline (call parser.fuzzy_match_title against all magazine title_slugs, select best match above 80% threshold, handle ambiguous matches with <10% score gap between top-2 → mark for manual) in backend/app/services/import_service.py
- [ ] T104 [US025] Implement download monitoring in download_service.py: poll all download clients for "pressarr" category items, detect status=completed, trigger import_service.import_file for each, handle download failures (retry up to 3 with exponential backoff) in backend/app/services/download_service.py

**Checkpoint**: Placing a magazine PDF in the download directory triggers automatic import: file is parsed, matched, renamed, moved to library, issue status updated, cover extracted.

---

## Phase 11: Calendar & Forecast (US-033 to US-038)

**Goal**: Calendar with forecast predictions for 6 months, reconciliation with real issues, delayed marking

**Independent Test**: `pytest tests/unit/test_calendar.py tests/integration/test_calendar_api.py -v` passes; Calendar page displays monthly view with forecasts

- [ ] T105 [P] [US034] Write calendar/forecast unit tests: forecast generation for all 7 frequencies (weekly=7d, biweekly=14d, monthly=1m, bimonthly=2m, quarterly=3m, semiannual=6m, annual=1y), irregular produces no forecast, delayed marking after 7 days, reconciliation (forecast replaced when real issue matches within ±7 day window) in backend/tests/unit/test_calendar.py
- [ ] T106 [P] [US033] Create calendar Pydantic schemas (CalendarResource with issueId/magazineId/title/coverUrl/date/status/isForecast flag, forecast entries have id=null) per api-calendar.md contract in backend/app/schemas/calendar.py
- [ ] T107 [US034] Implement calendar_service.py: generate_forecasts(magazine) → create Issue records with is_forecast=True for next 6 months based on frequency + last known issue date, reconcile_forecast(issue) → replace matching forecast when real issue imported (±7 day window on publication_date), mark_delayed() → update forecasts past due date by >7 days, skip/unskip forecast in backend/app/services/calendar_service.py
- [ ] T108 [US033] Implement /api/v1/calendar routes (GET with start/end date range + optional includeForecast + optional magazineId, POST /{id}/skip, POST /{id}/unskip) per api-calendar.md contract in backend/app/api/v1/calendar.py
- [ ] T109 [P] [US033] Write calendar API integration tests (date range query, forecast inclusion, skip/unskip, reconciliation after import) in backend/tests/integration/test_calendar_api.py
- [ ] T110 [P] [US033] Create calendar API client (getCalendar, skipForecast, unskipForecast) in frontend/src/api/calendar.ts
- [ ] T111 [US033] Create CalendarGrid component (month grid layout, day cells with magazine covers, solid border=confirmed issue, dashed border=forecast, click to navigate to issue, hover preview) in frontend/src/components/CalendarGrid.tsx
- [ ] T112 [US038] Create CalendarAgenda component (chronological list sorted by date, magazine cover + title + issue number, status badge, skip button for forecasts) in frontend/src/components/CalendarAgenda.tsx
- [ ] T113 [US033] Create Calendar page (month navigation prev/next, grid/agenda view toggle, filter by magazine/status, skip button on forecast entries) in frontend/src/pages/Calendar.tsx

**Checkpoint**: Calendar displays issues and forecasts for 6 months. Forecasts appear dashed. Monthly magazines show one entry per month. Skip/unskip works.

---

## Phase 12: Notifications (US-048 to US-052)

**Goal**: Multi-channel notification system with event-based dispatch

**Independent Test**: POST /api/v1/notification/test sends a test notification; notification_service dispatches to all enabled channels on import

- [ ] T114 [P] [US048] Create notification Pydantic schemas (NotificationResource with per-event toggles on_grab/on_download/on_import/on_upgrade/on_error, NotificationCreateResource, TestResult) per api-notification.md contract in backend/app/schemas/notification.py
- [ ] T115 [P] [US048] Implement abstract notification base (async send(event_type, payload) with magazine title/issue number/quality/cover_url, async test() → TestResult, format_payload per channel) in backend/app/notifications/base.py
- [ ] T116 [P] [US048] Implement Discord notification provider (HTTPX POST to webhook URL, embed with title/description/thumbnail from cover_url, color per event type) in backend/app/notifications/discord.py
- [ ] T117 [P] [US049] Implement Gotify notification provider (HTTPX POST to {serverUrl}/message with X-Gotify-Key header, priority from settings) in backend/app/notifications/gotify.py
- [ ] T118 [P] [US050] Implement Telegram notification provider (HTTPX POST to api.telegram.org/bot{token}/sendMessage or sendPhoto with chat_id, markdown formatting) in backend/app/notifications/telegram.py
- [ ] T119 [P] [US051] Implement generic webhook notification provider (HTTPX request with configurable method/URL/headers, JSON payload with all event data) in backend/app/notifications/webhook.py
- [ ] T120 [US052] Implement notification_service.py: dispatch(event_type, payload) → iterate all enabled Notification records → filter by event toggle → instantiate provider → send with error handling (log warning on failure, never block caller) in backend/app/services/notification_service.py
- [ ] T121 [US048] Implement /api/v1/notification routes (GET list, POST create, PUT update, DELETE, POST /test) per api-notification.md contract in backend/app/api/v1/notification.py
- [ ] T122 [US031] Integrate notification dispatch into import_service.py (on_import after successful import, on_grab after grab, on_upgrade after quality upgrade, on_error on import failure) and download_service.py (on_grab)
- [ ] T123 [P] [US048] Create notifications API client (getNotifications, createNotification, updateNotification, deleteNotification, testNotification) in frontend/src/api/notifications.ts
- [ ] T124 [US048] Create Notifications settings page (list channels with type icon, add/edit dialog per type: Discord webhook URL, Gotify server+token+priority, Telegram bot token+chat ID, Webhook URL+method+headers, per-event toggles, test button) in frontend/src/pages/Settings/Notifications.tsx

**Checkpoint**: Notifications are sent on grab/import/upgrade/error to all enabled channels. Test button sends a test notification successfully.

---

## Phase 13: Internet Archive (US-039 to US-042)

**Goal**: Search and download directly from Internet Archive Magazine Rack

**Independent Test**: GET /api/v1/search/internetarchive returns results; POST downloads a file that enters the import pipeline

- [ ] T125 [US041] Implement Internet Archive download client (HTTPX streaming download from archive.org/download/{id}/{file}, progress tracking via content-length, rate limit 1 req/sec via asyncio.Semaphore, save to /downloads, queue management in-memory) in backend/app/download_clients/internet_archive.py
- [ ] T126 [US039] Add /api/v1/search/internetarchive routes (GET search with query/magazineId params querying archive.org scrape API collection:magazinerack, POST download with identifier/issueId/preferredFormat triggering IA download client) per api-search.md contract in backend/app/api/v1/search.py
- [ ] T127 [US040] Implement IA matching logic: compare IA results against wanted issues by normalized title + date/number, propose matches with confidence score in backend/app/services/search_service.py
- [ ] T128 [US042] Add Internet Archive search button (issue-level and magazine-level) to MagazineDetail page and wire to /api/v1/search/internetarchive endpoints

**Checkpoint**: User can search Internet Archive for magazine issues, see results, and download directly. Downloaded files pass through the standard import pipeline.

---

## Phase 14: Activity & History (US-053 to US-057)

**Goal**: Real-time download queue, event history, and blocklist management

**Independent Test**: Queue page shows active downloads with live progress; History page shows past events with filters; Blocklist page allows unblocking

- [ ] T129 [P] [US054] Create history Pydantic schemas (HistoryResource with eventType/date/magazineId/issueId/details, BlocklistResource) per api-history.md and api-blocklist.md contracts in backend/app/schemas/history.py
- [ ] T130 [US054] Implement history_service.py: create_event(type, magazine_id, issue_id, details), paginated list with filters (eventType, magazineId, date range), auto-purge entries older than retention period (default 365 days, configurable) in backend/app/services/history_service.py
- [ ] T131 [US054] Implement /api/v1/history routes (GET paginated with eventType/magazineId filters) per api-history.md contract in backend/app/api/v1/history.py
- [ ] T132 [US055] Implement /api/v1/blocklist routes (GET paginated with magazineId filter, DELETE single, DELETE /bulk with ids array) per api-blocklist.md contract in backend/app/api/v1/blocklist.py
- [ ] T133 [US053] Implement /api/v1/queue routes (GET active downloads with progress/speed/eta per item from download clients, DELETE single with optional blocklist flag, DELETE /bulk) per api-queue.md contract in backend/app/api/v1/queue.py
- [ ] T134 [US053] Implement WebSocket queue updates (broadcast queue data every 5 seconds while downloads are active, include progress/speed/eta per item) in backend/app/api/v1/websocket.py
- [ ] T135 [P] [US053] Create queue API client (getQueue, removeFromQueue, bulkRemove) in frontend/src/api/queue.ts
- [ ] T136 [P] [US054] Create history API client (getHistory with filters) in frontend/src/api/history.ts
- [ ] T137 [P] [US053] Create useQueue hook (subscribe to WebSocket queue events, maintain local queue state, auto-refresh) in frontend/src/hooks/useQueue.ts
- [ ] T138 [P] [US053] Create QueueItem component (magazine title, issue number, progress bar with %, speed formatted, ETA, status badge, cancel/remove/blocklist buttons) in frontend/src/components/QueueItem.tsx
- [ ] T139 [US053] Create Queue page (list QueueItems, bulk selection, cancel all / remove all actions, empty state) in frontend/src/pages/Queue.tsx
- [ ] T140 [US054] Create History page (paginated table with date/event type icon/magazine/issue/details, filter dropdowns for eventType and magazine, date range picker) in frontend/src/pages/History.tsx
- [ ] T141 [US055] Create Blocklist page (paginated table with release title/magazine/indexer/date/reason, unblock button, bulk remove) in frontend/src/pages/Blocklist.tsx

**Checkpoint**: Queue shows live download progress via WebSocket. History displays all past events with working filters. Blocklist entries can be removed.

---

## Phase 15: Scheduled Tasks (US-020, US-023, US-057, US-063)

**Purpose**: Background jobs tying together search, download monitoring, history cleanup, and forecast refresh

- [ ] T142 [US020] Implement RSS sync scheduled task: query Prowlarr RSS for categories 7010+7020 → parse results through magazine_parser → match against wanted issues → auto-grab best release per quality profile → create history events in backend/app/scheduler/tasks.py
- [ ] T143 [US023] Implement download monitoring scheduled task: poll all download clients for "pressarr" items → detect completed → trigger import_service → detect failed → retry with backoff (max 3) → update WebSocket queue broadcast in backend/app/scheduler/tasks.py
- [ ] T144 [US057] Implement history purge scheduled task: delete History entries older than configured retention (default 365 days), run once per day in backend/app/scheduler/tasks.py
- [ ] T145 [US034] Implement forecast refresh scheduled task: recalculate all forecasts for monitored magazines, mark delayed forecasts (>7 days past due), reconcile with newly imported issues in backend/app/scheduler/tasks.py
- [ ] T146 [US063] Register all scheduled tasks in APScheduler with configurable intervals (RSS sync default 30min, download check default 30sec, history purge default 24h, forecast refresh default 24h, metadata refresh default 24h) in backend/app/scheduler/__init__.py

**Checkpoint**: RSS sync finds and grabs new releases automatically. Download monitoring detects completed downloads and triggers import. History is purged on schedule. Forecasts refresh daily.

---

## Phase 16: Ecosystem & Docker (US-070 to US-073)

**Goal**: Production Docker image, OpenAPI docs, Homepage/Homarr compatibility, first-run experience

**Independent Test**: `docker build -t pressarr .` succeeds; `docker run` starts and serves UI at port 8585; Homepage widget shows correct data

- [ ] T147 [US072] Create multi-stage Dockerfile: stage 1 — build frontend (node:20-alpine, npm ci, npm run build), stage 2 — production (python:3.12-slim, copy backend + built frontend, pip install, expose 8585, serve frontend via FastAPI StaticFiles, entrypoint uvicorn) in Dockerfile
- [ ] T148 [US072] Update docker-compose.yml for production (single service, volumes /config + /magazines + /downloads, port 8585, healthcheck via /api/v1/system/status) in docker-compose.yml
- [ ] T149 [US071] Configure FastAPI OpenAPI/Swagger documentation at /api/docs (title "Pressarr API", version from config, tag descriptions per resource) in backend/app/main.py
- [ ] T150 [US070] Verify /api/v1/system/status response format matches Homepage/Homarr widget expectations (camelCase, magazineCount, queueCount, diskSpace array) — adjust if needed in backend/app/api/v1/system.py
- [ ] T151 [US073] Finalize first-run setup in app lifespan: auto-create /config directory if missing → create default pressarr.yml → create SQLite DB → run Alembic migrations → create default quality profile → auto-generate API key → log API key to stdout → create default root folder /magazines if it exists in backend/app/main.py
- [ ] T152 [US062] Implement API key auth flow in frontend: detect 401 response → show API key input dialog → persist key in localStorage → retry failed request → clear key on logout in frontend/src/api/client.ts

**Checkpoint**: Docker image builds and runs. First start creates DB, generates API key, shows UI. Homepage widget integration works.

---

## Phase 17: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, edge case handling, and quality assurance

- [ ] T153 Run full test suite (`pytest tests/ -v --asyncio-mode=auto`) and fix any failures
- [ ] T154 [P] Verify all 15 edge cases (EC-001 to EC-015 from spec.md) are properly handled: Prowlarr unavailable → log warning no 500, download client disconnected → explicit error, Google Books quota → fallback to other sources, IA rate limit → backoff, unmatched file → /downloads/unmatched, simultaneous releases → best score wins, irregular frequency → no forecast, corrupted PDF → placeholder cover, unrecognized filename → partial result, disk full → keep in downloads, similar magazine names → ambiguous match handling, different numbering → date fallback
- [ ] T155 [P] Verify NFR compliance: API GET <200ms for single resources, list <500ms for 200 items (NFR-001), startup <10s (NFR-002), <256MB RAM idle (NFR-003), secrets never in logs or API responses (NFR-009)
- [ ] T156 [P] Complete i18n translations for all UI pages and components in frontend/src/i18n/{en.json, fr.json}
- [ ] T157 Run quickstart.md validation: follow backend setup, frontend setup, and Docker setup instructions end-to-end and verify they work as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Backend Foundation (Phase 2)**: Depends on Setup — BLOCKS all subsequent phases
- **Frontend Foundation (Phase 3)**: Depends on Setup — can run in PARALLEL with Phase 2
- **Parser (Phase 4)**: Depends on Phase 2 (test infrastructure) — can run in PARALLEL with Phase 3
- **Quality Profiles (Phase 5)**: Depends on Phase 2 (models + DB) and Phase 3 (frontend)
- **Magazine Management (Phase 6)**: Depends on Phase 5 (quality profiles FK)
- **Issue Management (Phase 7)**: Depends on Phase 6 (magazine FK)
- **Configuration (Phase 8)**: Depends on Phase 2 — can run in PARALLEL with Phases 5-7 (backend parts only)
- **Search & Download (Phase 9)**: Depends on Phase 7 (issues) + Phase 8 (indexers, download clients)
- **Import Pipeline (Phase 10)**: Depends on Phase 4 (parser) + Phase 7 (issues) + Phase 9 (download service)
- **Calendar (Phase 11)**: Depends on Phase 7 (issues) — can run in PARALLEL with Phases 9-10
- **Notifications (Phase 12)**: Depends on Phase 2 — can run in PARALLEL with Phases 5-11, but integration task (T122) depends on Phase 10
- **Internet Archive (Phase 13)**: Depends on Phase 9 (search) + Phase 10 (import)
- **Activity & History (Phase 14)**: Depends on Phase 9 (queue) + Phase 10 (import events)
- **Scheduled Tasks (Phase 15)**: Depends on Phases 9, 10, 11, 14 (all features they automate)
- **Ecosystem & Docker (Phase 16)**: Depends on all previous phases
- **Polish (Phase 17)**: Depends on all previous phases

### Critical Path

```
Phase 1 → Phase 2 → Phase 5 → Phase 6 → Phase 7 → Phase 9 → Phase 10 → Phase 15 → Phase 16 → Phase 17
                                                          ↑
                                          Phase 4 (parser)─┘
                                                          ↑
                                        Phase 8 (config)──┘
```

### Parallel Opportunities

```
After Phase 1:
  ├── Phase 2 (Backend Foundation)
  └── Phase 3 (Frontend Foundation)  [PARALLEL]

After Phase 2:
  ├── Phase 4 (Parser)               [PARALLEL]
  ├── Phase 8 (Configuration backend) [PARALLEL, backend parts T067-T082]
  └── Phase 12 (Notifications backend) [PARALLEL, backend parts T114-T121]

After Phase 7:
  ├── Phase 9 (Search)
  └── Phase 11 (Calendar)            [PARALLEL]

After Phase 10:
  ├── Phase 13 (Internet Archive)    [PARALLEL]
  └── Phase 14 (Activity & History)  [PARALLEL]
```

### Within Each Phase

- Tests MUST be written and FAIL before implementation (Constitution Art. III)
- Models/schemas before services
- Services before API routes
- Backend before frontend (for same feature)
- Story complete before moving to next priority

---

## Parallel Example: Phase 6 (Magazine Management)

```bash
# Launch tests and contracts in parallel:
Task: "Write magazine API integration tests in backend/tests/integration/test_magazine_api.py"     # T042
Task: "Write metadata provider contract tests in backend/tests/contract/test_metadata.py"          # T043

# Launch schemas and metadata providers in parallel:
Task: "Create magazine Pydantic schemas in backend/app/schemas/magazine.py"                        # T044
Task: "Implement metadata provider base in backend/app/metadata/base.py"                           # T048
Task: "Implement Google Books provider in backend/app/metadata/google_books.py"                     # T049
Task: "Implement Internet Archive provider in backend/app/metadata/internet_archive.py"             # T050

# Sequential: service → routes (depend on schemas + providers)
Task: "Implement magazine_service.py"                                                               # T045
Task: "Implement /api/v1/magazine routes"                                                           # T046

# Launch frontend in parallel:
Task: "Create magazines API client in frontend/src/api/magazines.ts"                                # T051
Task: "Create MagazineCard component"                                                               # T052

# Sequential: pages (depend on API client + components)
Task: "Create Library page"                                                                         # T053
Task: "Create AddMagazine page"                                                                     # T054
Task: "Create MagazineDetail page"                                                                  # T055
```

---

## Implementation Strategy

### MVP First (Phases 1-7 Only)

1. **Phase 1**: Setup → project structure ready
2. **Phase 2**: Backend Foundation → API shell running
3. **Phase 3**: Frontend Foundation → dark theme UI navigable (parallel with Phase 2)
4. **Phase 4**: Parser → filename parsing working (25+ tests green)
5. **Phase 5**: Quality Profiles → quality hierarchy configured
6. **Phase 6**: Magazine Management → add/view/edit magazines with metadata search
7. **Phase 7**: Issue Management → view issues, scan folders, extract covers
8. **STOP and VALIDATE**: User can add a magazine, see its issues, scan existing files

### Full Automation (Phases 8-10)

9. **Phase 8**: Configuration → Prowlarr + download clients connected
10. **Phase 9**: Search → search indexers, grab releases
11. **Phase 10**: Import Pipeline → automatic download → import → organize
12. **VALIDATE**: SC-001 — Magazine added → issues found → downloaded → organized automatically within 30 min

### Complete Feature Set (Phases 11-17)

13. **Phase 11**: Calendar → forecast predictions for 6 months (SC-002)
14. **Phase 12**: Notifications → alerts on grab/import/error
15. **Phase 13**: Internet Archive → free magazine downloads
16. **Phase 14**: Activity → queue/history/blocklist UI
17. **Phase 15**: Scheduled Tasks → fully autonomous operation
18. **Phase 16**: Docker → production deployment (SC-003, SC-004)
19. **Phase 17**: Polish → edge cases, NFRs, i18n, quickstart validation

---

## Summary

| Metric | Count |
|--------|-------|
| Total tasks | 157 |
| Phases | 17 |
| Setup tasks | 5 |
| Foundational tasks (backend + frontend) | 24 |
| User Story tasks | 121 |
| Polish tasks | 5 |
| Integration test tasks | 10 |
| Unit test tasks | 3 |
| Contract test tasks | 4 |
| Frontend page tasks | 17 |
| Frontend component tasks | 10 |
| Parallel opportunities (within phases) | 72 tasks marked [P] |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks within the same phase
- [USxxx] label maps task to specific user story from spec.md for traceability
- Each phase should be independently completable and testable at its checkpoint
- Constitution Art. III requires tests before/during implementation — test tasks are listed first in each phase
- All external API calls use HTTPX (Art. IV §4.5), all I/O is async (Art. IV §4.1)
- API responses use camelCase (Art. II §2.1), backend uses snake_case (Art. IX §9.1)
- Commit after each task or logical group using Conventional Commits (Art. IX §9.4)
