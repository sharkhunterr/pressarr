"""Test fixtures: async in-memory SQLite, AsyncClient, test config."""

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import Config
from app.database import Base
from app.dependencies import set_config


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    """Create an async in-memory SQLite engine for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Import all models so Base.metadata has all tables
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session for tests."""
    factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_config(tmp_path) -> Config:
    """Create a test configuration."""
    os.environ["PRESSARR__CONFIG_PATH"] = str(tmp_path / "pressarr.yml")
    os.environ["PRESSARR__DB_PATH"] = str(tmp_path / "test.db")
    config = Config()
    config.auth_enabled = False
    set_config(config)
    return config


@pytest_asyncio.fixture
async def client(test_engine, test_config) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with in-memory database."""
    import app.database as db_module

    # Patch the module-level engine and session factory
    db_module.engine = test_engine
    db_module.async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
