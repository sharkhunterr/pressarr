"""FastAPI application factory with lifespan and middleware."""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Config
from app.database import close_database, init_database
from app.dependencies import get_config, set_config

logger = logging.getLogger(__name__)

# Auth-exempt paths
AUTH_EXEMPT_PATHS = {
    "/api/v1/system/status",
    "/api/v1/system/logs",
    "/api/docs",
    "/api/redoc",
    "/openapi.json",
}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Optional API key authentication via X-Api-Key header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        config = get_config()

        # Skip auth if disabled
        if not config.auth_enabled or not config.api_key:
            return await call_next(request)

        # Skip exempt paths
        path = request.url.path
        if path in AUTH_EXEMPT_PATHS or path.startswith("/api/docs"):
            return await call_next(request)

        # Skip non-API paths (frontend static files)
        if not path.startswith("/api/"):
            return await call_next(request)

        # Check API key
        api_key = request.headers.get("X-Api-Key")
        if api_key != config.api_key:
            return Response(
                content='{"detail":"Unauthorized"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    # Load config
    config = Config()
    set_config(config)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Add in-memory ring-buffer handler for remote log viewing
    from app.log_buffer import log_buffer_handler

    logging.getLogger().addHandler(log_buffer_handler)

    # Auto-create /config directory
    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    config.db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create default pressarr.yml if not exists
    if not config.config_path.exists():
        config.save()
        logger.info("Default configuration created at %s", config.config_path)

    # Initialize database
    await init_database(str(config.db_path))

    # Auto-create tables (Alembic used for dev migrations)
    import app.models  # noqa: F401 — register all models
    from app.database import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add new columns to existing tables (SQLite ALTER TABLE)
        await conn.run_sync(_migrate_add_columns)
    logger.info("Database tables ensured")

    # Auto-generate API key on first start
    if not config.api_key:
        key = config.generate_api_key()
        logger.info("API key generated: %s...%s", key[:4], key[-4:])

    # Create default quality profile if none exists
    await _create_default_quality_profile()

    # Create default root folder /magazines if the directory exists
    await _create_default_root_folder()

    # Load persistent grab registry
    from app.services.download_service import _load_registry
    _load_registry()

    # Start scheduler
    from app.scheduler import start_scheduler
    start_scheduler()

    logger.info("Pressarr started on port %d", config.port)

    yield

    # Shutdown
    from app.scheduler import stop_scheduler
    stop_scheduler()
    await close_database()
    logger.info("Pressarr stopped")


def _migrate_add_columns(connection) -> None:
    """Add new columns to existing tables (safe for SQLite)."""
    import sqlalchemy as sa
    migrations = [
        ("download_client", "remote_path", "VARCHAR(500)"),
        ("download_client", "local_path", "VARCHAR(500)"),
        ("history", "data", "TEXT"),
        ("history", "pack_id", "INTEGER REFERENCES pack(id) ON DELETE SET NULL"),
        ("indexer_config", "indexer_overrides", "TEXT NOT NULL DEFAULT '{}'"),
    ]
    for table, column, col_type in migrations:
        try:
            connection.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            logger.info("Migration: added %s.%s", table, column)
        except Exception:
            pass  # Column already exists


async def _create_default_quality_profile() -> None:
    """Create the default quality profile if none exists."""
    from sqlalchemy import select

    from app.database import async_session_factory

    if async_session_factory is None:
        return

    async with async_session_factory() as session:
        from app.models.quality_profile import QualityProfile, QualityProfileItem

        result = await session.execute(select(QualityProfile))
        if result.scalars().first() is not None:
            return

        profile = QualityProfile(
            name="Default",
            cutoff="pdf_hq",
            is_default=True,
        )
        session.add(profile)
        await session.flush()

        qualities = [
            ("unknown", True, 0),
            ("scan", True, 1),
            ("pdf_lq", True, 2),
            ("pdf_hq", True, 3),
            ("retail", True, 4),
            ("truepdf", True, 5),
        ]
        for quality, allowed, order in qualities:
            item = QualityProfileItem(
                quality_profile_id=profile.id,
                quality=quality,
                allowed=allowed,
                sort_order=order,
            )
            session.add(item)

        await session.commit()
        logger.info("Default quality profile created")


async def _create_default_root_folder() -> None:
    """Create a default root folder /magazines if the directory exists on the filesystem."""
    magazines_path = Path("/magazines")
    if not magazines_path.is_dir():
        return

    from sqlalchemy import select

    from app.database import async_session_factory

    if async_session_factory is None:
        return

    async with async_session_factory() as session:
        from app.models.root_folder import RootFolder

        result = await session.execute(select(RootFolder))
        if result.scalars().first() is not None:
            return

        folder = RootFolder(
            path=str(magazines_path),
            is_default=True,
        )
        session.add(folder)
        await session.commit()
        logger.info("Default root folder created: %s", magazines_path)


tags_metadata = [
    {"name": "Magazines", "description": "Magazine collection management"},
    {"name": "Issues", "description": "Issue and file management"},
    {"name": "Search", "description": "Search indexers and grab releases"},
    {"name": "Calendar", "description": "Calendar with forecast predictions"},
    {"name": "Queue", "description": "Download queue management"},
    {"name": "History", "description": "Event history"},
    {"name": "Blocklist", "description": "Blocked releases"},
    {"name": "Quality Profiles", "description": "Quality profile management"},
    {"name": "Notifications", "description": "Notification channel management"},
    {"name": "Download Clients", "description": "Download client configuration"},
    {"name": "Indexers", "description": "Indexer configuration"},
    {"name": "Root Folders", "description": "Library root folder management"},
    {"name": "Settings", "description": "Application settings"},
    {"name": "System", "description": "System status and health"},
    {"name": "Commands", "description": "Command execution"},
    {"name": "WebSocket", "description": "Real-time updates"},
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pressarr API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/openapi.json",
        openapi_tags=tags_metadata,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API key auth middleware
    app.add_middleware(ApiKeyMiddleware)

    # Register API routes
    from app.api.v1.blocklist import router as blocklist_router
    from app.api.v1.calendar import router as calendar_router
    from app.api.v1.command import router as command_router
    from app.api.v1.download_client import router as download_client_router
    from app.api.v1.history import router as history_router
    from app.api.v1.indexer import router as indexer_router
    from app.api.v1.issue import router as issue_router
    from app.api.v1.magazine import router as magazine_router
    from app.api.v1.notification import router as notification_router
    from app.api.v1.pack import router as pack_router
    from app.api.v1.quality_profile import router as quality_router
    from app.api.v1.queue import router as queue_router
    from app.api.v1.root_folder import router as root_folder_router
    from app.api.v1.search import router as search_router
    from app.api.v1.settings import router as settings_router
    from app.api.v1.system import router as system_router
    from app.api.v1.websocket import router as ws_router

    app.include_router(command_router)
    app.include_router(quality_router)
    app.include_router(system_router)
    app.include_router(root_folder_router)
    app.include_router(indexer_router)
    app.include_router(download_client_router)
    app.include_router(notification_router)
    app.include_router(history_router)
    app.include_router(blocklist_router)
    app.include_router(ws_router)
    app.include_router(magazine_router)
    app.include_router(pack_router)
    app.include_router(issue_router)
    app.include_router(search_router)
    app.include_router(calendar_router)
    app.include_router(queue_router)
    app.include_router(settings_router)

    # Serve frontend static files (after all API routes)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static-assets", StaticFiles(directory=static_dir), name="static-assets")

        # SPA catch-all: serve index.html for any non-API route
        from fastapi.responses import FileResponse

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # Serve actual static files (js, css, images, etc.)
            file_path = os.path.join(static_dir, full_path)
            if full_path and os.path.isfile(file_path):
                return FileResponse(file_path)
            # Everything else gets index.html (SPA routing)
            return FileResponse(os.path.join(static_dir, "index.html"))

    return app


app = create_app()
