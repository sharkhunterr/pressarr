"""FastAPI application factory with async lifespan for Pressarr."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import SystemConfig, load_config, write_default_config
from app.database import close_database, init_database
from app.logging import setup_logging

logger = logging.getLogger(__name__)


def _check_config_writable(config_dir: str) -> None:
    """Check that the config directory is writable. Exit if not."""
    path = Path(config_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        test_file.touch()
        test_file.unlink()
    except OSError as e:
        logger.error("Config directory '%s' is not writable: %s", config_dir, e)
        sys.exit(1)


def _run_migrations(db_path: str) -> None:
    """Run Alembic migrations programmatically."""
    alembic_cfg = AlembicConfig()
    # Find alembic directory relative to this file
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception as e:
        logger.error("Failed to run database migrations: %s", e)
        sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    config: SystemConfig = app.state.config

    # Check config dir is writable
    _check_config_writable(config.config_dir)

    # Write default config on first start
    write_default_config(config)

    # Setup logging
    setup_logging(config.log_level, config.config_dir)

    # Run database migrations (sync — Alembic doesn't support async natively)
    _run_migrations(config.db_path)

    # Initialize async database engine
    try:
        await init_database(config.db_path)
    except Exception as e:
        logger.error("Cannot initialize database at '%s': %s", config.db_path, e)
        sys.exit(1)

    # Store start time for uptime calculation
    app.state.start_time = datetime.now(timezone.utc)

    logger.info(
        "Pressarr v0.1.0 started on %s:%d",
        config.server_host,
        config.server_port,
    )

    yield

    # Shutdown
    await close_database()
    logger.info("Pressarr shut down")


def create_app(config: SystemConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = load_config()

    app = FastAPI(
        title="Pressarr",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.config = config

    # Mount API router
    app.include_router(api_router)

    # Mount frontend static files in production
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


# Default app instance for uvicorn
app = create_app()
