# Quickstart: Pressarr Development

**Branch**: `001-pressarr` | **Date**: 2026-02-26

---

## Prerequisites

- Python 3.12+
- Node.js 20+ / npm 10+
- Git

---

## Backend Setup

```bash
cd backend

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8585
```

The backend starts at `http://localhost:8585`. API docs at `/api/docs`.

### Backend Dependencies (requirements.txt)

```
fastapi>=0.109,<1
uvicorn[standard]>=0.27
sqlalchemy>=2.0,<2.1
aiosqlite>=0.20.0
alembic>=1.13
pydantic>=2.5,<3
httpx>=0.27
APScheduler>=3.10,<4
PyMuPDF>=1.24
rapidfuzz>=3.6
python-multipart>=0.0.6
websockets>=12.0
pyyaml>=6.0
```

### Running Tests

```bash
pytest tests/ -v --asyncio-mode=auto
```

Test dependencies: `pytest`, `pytest-asyncio`, `httpx` (for `AsyncClient`).

---

## Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server (proxies API to backend)
npm run dev
```

The frontend starts at `http://localhost:5173` with HMR. API calls are proxied to `localhost:8585`.

### Frontend Dependencies

Initialized via:
```bash
npm create vite@latest . -- --template react-ts
npx shadcn@latest init
npm install react-i18next i18next @tanstack/react-query react-router-dom
```

### Vite Proxy Config

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8585',
      '/ws': { target: 'ws://localhost:8585', ws: true }
    }
  }
})
```

---

## Docker Setup

```bash
# Build
docker build -t pressarr .

# Run
docker run -d \
  --name pressarr \
  -p 8585:8585 \
  -v ./config:/config \
  -v ./magazines:/magazines \
  -v ./downloads:/downloads \
  pressarr
```

---

## Project Layout

```
backend/
  app/
    main.py              # FastAPI app factory + lifespan
    config.py            # YAML + env config
    database.py          # SQLAlchemy async engine
    dependencies.py      # FastAPI Depends() providers
    models/              # SQLAlchemy ORM models
    schemas/             # Pydantic v2 schemas
    services/            # Business logic (1 file = 1 domain)
    api/v1/              # Route handlers
    indexers/             # Prowlarr client
    download_clients/    # Deluge, qBit, Transmission, SABnzbd, NZBGet
    metadata/            # Google Books, Internet Archive
    notifications/       # Discord, Gotify, Telegram, Webhook
    parser/              # Magazine filename parser
    scheduler/           # APScheduler tasks
  tests/
    unit/                # Parser (25+ cases), quality, calendar
    integration/         # API endpoints with in-memory SQLite
    contract/            # Mocked external API responses
  alembic/               # Database migrations

frontend/
  src/
    api/                 # API client functions
    components/          # React components + shadcn/ui
    pages/               # Route pages
    hooks/               # Custom hooks (WebSocket, Queue)
    i18n/                # EN/FR translations
```

---

## Key Conventions

- **Backend**: snake_case functions/variables, PascalCase classes, UPPER_CASE constants
- **API responses**: camelCase JSON (Pydantic alias_generator)
- **Routes**: `/api/v1/{resource}` singular, kebab-case
- **Files**: one file = one concept (`magazine_service.py`, not `services.py`)
- **Call depth**: route → service → query (max 3 levels)
- **Functions**: max 50 lines, one responsibility
- **Commits**: Conventional Commits (`feat:`, `fix:`, `test:`, etc.)

---

## Environment Variables

All prefixed with `PRESSARR__` (double underscore as separator):

| Variable | Default | Description |
|----------|---------|-------------|
| `PRESSARR__PORT` | 8585 | Listen port |
| `PRESSARR__LOG_LEVEL` | info | Log level |
| `PRESSARR__DB_PATH` | /config/pressarr.db | Database file path |
| `PRESSARR__CONFIG_PATH` | /config/pressarr.yml | Config file path |

---

## First Run Behavior

On first start with no existing database:
1. SQLite database created at `/config/pressarr.db`
2. Alembic migrations applied automatically
3. Default quality profile created ("Default" — all qualities allowed, cutoff at PDF-HQ)
4. API key auto-generated and logged
5. Config file created at `/config/pressarr.yml`
6. Web UI accessible immediately at port 8585
