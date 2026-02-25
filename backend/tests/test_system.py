"""Tests for GET /api/v1/system/status endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_status_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/status")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_contains_version(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/status")
    data = response.json()
    assert "version" in data
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_status_contains_uptime(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/status")
    data = response.json()
    assert "uptime" in data
    assert isinstance(data["uptime"], int)
    assert data["uptime"] >= 0


@pytest.mark.asyncio
async def test_status_contains_counts_at_zero(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/status")
    data = response.json()
    assert data["magazineCount"] == 0
    assert data["issueCount"] == 0
    assert data["issueFileCount"] == 0


@pytest.mark.asyncio
async def test_status_uses_camel_case_fields(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/status")
    data = response.json()
    # Must use camelCase (Sonarr/Radarr convention)
    assert "startTime" in data
    assert "magazineCount" in data
    assert "issueCount" in data
    assert "issueFileCount" in data
    # Must NOT have snake_case
    assert "start_time" not in data
    assert "magazine_count" not in data
