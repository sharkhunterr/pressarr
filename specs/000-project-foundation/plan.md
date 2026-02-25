# Implementation Plan: Project Foundation

**Branch**: `000-project-foundation` | **Date**: 2026-02-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `.specify/specs/000-project-foundation/spec.md`

## Summary

Mettre en place le socle technique complet de Pressarr : structure du projet (backend Python + frontend React), base de données SQLite avec migrations automatiques, configuration hiérarchique YAML + env, API REST de base avec endpoint de santé, frontend minimal dark theme, et Dockerfile standalone. Ce socle est le prérequis de toutes les features suivantes.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Uvicorn, HTTPX, APScheduler (backend) — React 18, Vite, Tailwind CSS, shadcn/ui, TanStack Query (frontend)
**Storage**: SQLite via SQLAlchemy 2.0 async (aiosqlite), stored at /config/pressarr.db
**Testing**: pytest, pytest-asyncio (backend) — Vitest (frontend)
**Target Platform**: Linux Docker container (amd64/arm64), self-hosted NAS
**Project Type**: Web application (backend API + frontend SPA)
**Performance Goals**: Startup < 30s, API response < 200ms p95
**Constraints**: Zero-config first start, no cloud dependency, single Docker image
**Scale/Scope**: Single user, < 200 magazines, SQLite sufficient

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Rule | Status | Notes |
|---------|------|--------|-------|
| I - Architecture Modulaire | Backend/frontend séparation | PASS | backend/ et frontend/ distincts |
| I - Architecture Modulaire | Modèles séparés des schémas | PASS | models/ vs schemas/ |
| I - Architecture Modulaire | Frontend via API uniquement | PASS | SPA communique via /api/v1/* |
| II - Écosystème *arr | API /api/v1/{resource} | PASS | /api/v1/system/status |
| II - Écosystème *arr | Port 8585, volumes Docker | PASS | Configuré par défaut |
| IV - Async-First | I/O async obligatoire | PASS | FastAPI + SQLAlchemy async |
| IV - Type Safety | Type hints obligatoires | PASS | mypy strict |
| IV - Type Safety | Pydantic v2 pour validation | PASS | Schémas API Pydantic |
| V - Simplicité | Max 3 niveaux d'appel | PASS | route → service → query |
| V - Simplicité | Pas de patterns Enterprise | PASS | Utilisation directe FastAPI/SQLAlchemy |
| VI - Docker-Native | Image standalone | PASS | Multi-stage Dockerfile |
| VI - Docker-Native | Config YAML + env override | PASS | PRESSARR__* variables |
| VI - Docker-Native | SQLite dans /config | PASS | /config/pressarr.db |
| VI - Docker-Native | Zero-config premier démarrage | PASS | Auto-create DB + API key |
| VII - UI Sombre | Dark theme par défaut | PASS | zinc-900/950 + #E85D04 accent |
| VIII - Résilience | Erreurs ne crashent pas | PASS | Startup errors = clean message |
| IX - Conventions | snake_case, PascalCase, Conventional Commits | PASS | Enforced by ruff + config |

All gates PASS. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/000-project-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory, lifespan, static mount
│   ├── config.py            # YAML + env config loading
│   ├── database.py          # SQLAlchemy async engine + session
│   ├── models/
│   │   ├── __init__.py
│   │   └── base.py          # SQLAlchemy declarative base
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── system.py        # SystemStatus Pydantic schema
│   └── api/
│       ├── __init__.py
│       ├── router.py         # /api/v1 root router
│       └── system.py         # /api/v1/system/status endpoint
├── alembic/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py           # Fixtures: async client, in-memory DB
│   └── test_system.py        # Tests for /api/v1/system/status
├── pyproject.toml
└── requirements.txt

frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx               # Root layout, router
│   ├── components/
│   │   └── ui/               # shadcn/ui components
│   ├── pages/
│   │   └── HomePage.tsx      # Empty state page
│   ├── lib/
│   │   └── api.ts            # API client (fetch wrapper)
│   └── styles/
│       └── globals.css       # Tailwind + dark theme tokens
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json

Dockerfile                    # Multi-stage: build frontend → serve with backend
docker-compose.yml            # Dev/example compose file
```

**Structure Decision**: Web application (Option 2) — backend/ and frontend/ at root. Backend serves the frontend build as static files in production. The Dockerfile uses a multi-stage build: Node stage builds the frontend, Python stage copies the build output and runs Uvicorn.

## Edge Cases Implementation Notes

Les cas limites suivants (de la spec) DOIVENT être implémentés dans le code de démarrage :

| Edge Case | Fichier concerné | Comportement attendu |
|-----------|-------------------|---------------------|
| /config non accessible en écriture | app/main.py (lifespan) | Message d'erreur clair + exit code 1 |
| YAML invalide (valeurs incorrectes) | app/config.py | Log warning + fallback sur defaults pour les champs invalides |
| Base de données corrompue | app/database.py | Message d'erreur clair au démarrage + exit code 1 |
| Port déjà occupé | app/main.py (Uvicorn) | Message d'erreur explicite (Uvicorn gère nativement) |

## Complexity Tracking

No violations detected. No justifications needed.
