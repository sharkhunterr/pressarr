"""Integration tests for issue API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.issue import Issue
from app.models.issue_file import IssueFile
from app.models.magazine import Magazine
from app.models.quality_profile import QualityProfile
from app.models.root_folder import RootFolder


@pytest_asyncio.fixture
async def seed_data(test_session: AsyncSession):
    """Seed a magazine with issues for testing."""
    root = RootFolder(path="/magazines")
    test_session.add(root)
    await test_session.flush()

    profile = QualityProfile(name="Default", cutoff="pdf_hq", is_default=True)
    test_session.add(profile)
    await test_session.flush()

    magazine = Magazine(
        title="Science et Vie",
        title_slug="science-et-vie",
        frequency="monthly",
        monitored=True,
        root_folder_id=root.id,
        quality_profile_id=profile.id,
    )
    test_session.add(magazine)
    await test_session.flush()

    issues = []
    for i in range(1, 6):
        issue = Issue(
            magazine_id=magazine.id,
            number=1280 + i,
            year=2025,
            month=i,
            status="wanted" if i <= 3 else "missing",
            monitored=i <= 3,
        )
        test_session.add(issue)
        issues.append(issue)
    await test_session.flush()

    # Add a file to issue 1
    issue_file = IssueFile(
        issue_id=issues[0].id,
        magazine_id=magazine.id,
        path="/magazines/Science et Vie/SEV-1281.pdf",
        relative_path="Science et Vie/SEV-1281.pdf",
        size=52_000_000,
        format="pdf",
        quality="truepdf",
        original_filename="SEV-1281.pdf",
    )
    test_session.add(issue_file)
    issues[0].status = "available"
    await test_session.flush()
    await test_session.commit()

    return {"magazine": magazine, "issues": issues, "file": issue_file}


@pytest.mark.asyncio
async def test_list_issues_by_magazine(client: AsyncClient, seed_data):
    """List issues filtered by magazineId."""
    mag = seed_data["magazine"]
    resp = await client.get(f"/api/v1/issue?magazineId={mag.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    # First should be highest number (descending order)
    assert data[0]["number"] >= data[-1]["number"]


@pytest.mark.asyncio
async def test_list_issues_by_status(client: AsyncClient, seed_data):
    """List issues filtered by status."""
    mag = seed_data["magazine"]
    resp = await client.get(f"/api/v1/issue?magazineId={mag.id}&status=wanted")
    assert resp.status_code == 200
    data = resp.json()
    assert all(d["status"] == "wanted" for d in data)


@pytest.mark.asyncio
async def test_get_issue(client: AsyncClient, seed_data):
    """Get a single issue by ID."""
    issue = seed_data["issues"][0]
    resp = await client.get(f"/api/v1/issue/{issue.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == issue.id
    assert data["number"] == 1281
    assert data["file"] is not None
    assert data["file"]["format"] == "pdf"


@pytest.mark.asyncio
async def test_get_issue_not_found(client: AsyncClient, seed_data):
    """Get a non-existent issue returns 404."""
    resp = await client.get("/api/v1/issue/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_monitored(client: AsyncClient, seed_data):
    """Toggle monitoring on an issue."""
    issue = seed_data["issues"][3]  # monitored=False, status=missing
    resp = await client.put(
        f"/api/v1/issue/{issue.id}",
        json={"monitored": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["monitored"] is True
    assert data["status"] == "wanted"


@pytest.mark.asyncio
async def test_unmonitor_changes_status(client: AsyncClient, seed_data):
    """Unmonitoring a wanted issue changes status to missing."""
    issue = seed_data["issues"][1]  # monitored=True, status=wanted
    resp = await client.put(
        f"/api/v1/issue/{issue.id}",
        json={"monitored": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["monitored"] is False
    assert data["status"] == "missing"


@pytest.mark.asyncio
async def test_batch_monitor(client: AsyncClient, seed_data):
    """Batch monitor multiple issues."""
    ids = [seed_data["issues"][3].id, seed_data["issues"][4].id]
    resp = await client.put(
        "/api/v1/issue/monitor",
        json={"issueIds": ids, "monitored": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(d["monitored"] is True for d in data)


@pytest.mark.asyncio
async def test_delete_issue_file_not_found(client: AsyncClient, seed_data):
    """Delete file for issue without file returns 404."""
    issue = seed_data["issues"][2]  # no file
    resp = await client.delete(f"/api/v1/issue/{issue.id}/file")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cover_not_found(client: AsyncClient, seed_data):
    """Get cover for issue without cover returns 404."""
    issue = seed_data["issues"][1]  # no cover
    resp = await client.get(f"/api/v1/issue/{issue.id}/cover")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_issue_with_file_has_nested_resource(client: AsyncClient, seed_data):
    """Issue with file returns nested issueFile data."""
    issue = seed_data["issues"][0]  # has file
    resp = await client.get(f"/api/v1/issue/{issue.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["file"] is not None
    assert data["file"]["size"] == 52_000_000
    assert data["file"]["quality"] == "truepdf"
