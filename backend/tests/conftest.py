"""Test fixtures for Pressarr backend tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import SystemConfig
from app.main import create_app


@pytest.fixture
def config(tmp_path) -> SystemConfig:
    """Create a test configuration using a temporary directory."""
    return SystemConfig(
        config_dir=str(tmp_path / "config"),
        db_path=str(tmp_path / "config" / "pressarr.db"),
        server_port=8585,
        api_key="test-api-key-1234567890abcdef",
    )


@pytest.fixture
async def app(config: SystemConfig):
    """Create a test FastAPI application."""
    test_app = create_app(config=config)
    # Manually set start_time (normally done in lifespan)
    test_app.state.start_time = datetime.now(timezone.utc)
    return test_app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
