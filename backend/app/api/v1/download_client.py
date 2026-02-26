"""Download client configuration API routes — /api/v1/downloadclient."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.download_clients.base import DownloadClientBase
from app.download_clients.deluge import DelugeClient
from app.download_clients.nzbget import NZBGetClient
from app.download_clients.qbittorrent import QBittorrentClient
from app.download_clients.sabnzbd import SABnzbdClient
from app.download_clients.transmission import TransmissionClient
from app.models.download_client import DownloadClient
from app.schemas.download import (
    DownloadClientCreateResource,
    DownloadClientResource,
    DownloadClientUpdateResource,
    TestResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/downloadclient", tags=["Download Clients"])


def _build_client(
    client_type: str,
    host: str,
    port: int,
    use_ssl: bool = False,
    username: str | None = None,
    password: str | None = None,
    api_key: str | None = None,
) -> DownloadClientBase:
    """Build a download client instance from configuration parameters."""
    match client_type:
        case "deluge":
            return DelugeClient(
                host=host, port=port, password=password or "", use_ssl=use_ssl
            )
        case "qbittorrent":
            return QBittorrentClient(
                host=host,
                port=port,
                username=username or "admin",
                password=password or "",
                use_ssl=use_ssl,
            )
        case "transmission":
            return TransmissionClient(
                host=host,
                port=port,
                username=username,
                password=password,
                use_ssl=use_ssl,
            )
        case "sabnzbd":
            return SABnzbdClient(
                host=host, port=port, api_key=api_key or "", use_ssl=use_ssl
            )
        case "nzbget":
            return NZBGetClient(
                host=host,
                port=port,
                username=username or "nzbget",
                password=password or "tegbzn6789",
                use_ssl=use_ssl,
            )
        case _:
            raise ValueError(f"Unsupported client type: {client_type}")


@router.get("", response_model=list[DownloadClientResource])
async def list_download_clients(
    db: AsyncSession = Depends(get_db),
) -> list[DownloadClientResource]:
    """List all download clients (password/apiKey excluded)."""
    result = await db.execute(select(DownloadClient))
    clients = result.scalars().all()
    return [DownloadClientResource.model_validate(c) for c in clients]


@router.post("", response_model=DownloadClientResource, status_code=201)
async def create_download_client(
    body: DownloadClientCreateResource,
    db: AsyncSession = Depends(get_db),
) -> DownloadClientResource:
    """Create a new download client configuration."""
    client = DownloadClient(
        name=body.name,
        client_type=body.client_type,
        protocol=body.protocol,
        host=body.host,
        port=body.port,
        use_ssl=body.use_ssl,
        username=body.username,
        password=body.password,
        api_key=body.api_key,
        category=body.category,
        is_default=body.is_default,
        priority=body.priority,
    )
    db.add(client)
    await db.flush()
    return DownloadClientResource.model_validate(client)


@router.put("/{client_id}", response_model=DownloadClientResource)
async def update_download_client(
    client_id: int,
    body: DownloadClientUpdateResource,
    db: AsyncSession = Depends(get_db),
) -> DownloadClientResource:
    """Update an existing download client configuration."""
    client = await db.get(DownloadClient, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Download client not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    await db.flush()
    return DownloadClientResource.model_validate(client)


@router.delete("/{client_id}", status_code=204)
async def delete_download_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a download client configuration."""
    client = await db.get(DownloadClient, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Download client not found")
    await db.delete(client)
    await db.flush()


@router.post("/test", response_model=TestResult)
async def test_download_client(
    body: DownloadClientCreateResource,
) -> TestResult:
    """Test connection to a download client."""
    try:
        dl_client = _build_client(
            client_type=body.client_type,
            host=body.host,
            port=body.port,
            use_ssl=body.use_ssl,
            username=body.username,
            password=body.password,
            api_key=body.api_key,
        )
    except ValueError as e:
        return TestResult(is_valid=False, message=str(e))

    try:
        is_valid, message = await dl_client.test_connection()
        return TestResult(is_valid=is_valid, message=message)
    finally:
        await dl_client.close()
