"""Settings API routes — /api/v1/settings."""

import logging

import httpx
from fastapi import APIRouter, Depends

from app.dependencies import get_config
from app.schemas import CamelModel
from app.schemas.download import TestResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


# ---------------------------------------------------------------------------
# General settings
# ---------------------------------------------------------------------------


class GeneralSettingsResource(CamelModel):
    port: int
    log_level: str
    auth_enabled: bool
    scheduled_task_interval: int


class GeneralSettingsUpdateResource(CamelModel):
    port: int | None = None
    log_level: str | None = None
    auth_enabled: bool | None = None
    scheduled_task_interval: int | None = None


@router.get("/general", response_model=GeneralSettingsResource)
async def get_general_settings(config=Depends(get_config)):
    return GeneralSettingsResource(
        port=config.port,
        log_level=config.log_level,
        auth_enabled=config.auth_enabled,
        scheduled_task_interval=config.rss_sync_interval // 60,
    )


@router.post("/general", response_model=GeneralSettingsResource)
async def save_general_settings(
    body: GeneralSettingsUpdateResource,
    config=Depends(get_config),
):
    if body.port is not None:
        config.port = body.port
    if body.log_level is not None:
        config.log_level = body.log_level
    if body.auth_enabled is not None:
        config.auth_enabled = body.auth_enabled
    if body.scheduled_task_interval is not None:
        config.rss_sync_interval = body.scheduled_task_interval * 60
    config.save()

    return GeneralSettingsResource(
        port=config.port,
        log_level=config.log_level,
        auth_enabled=config.auth_enabled,
        scheduled_task_interval=config.rss_sync_interval // 60,
    )


# ---------------------------------------------------------------------------
# Naming template
# ---------------------------------------------------------------------------


class NamingTemplateResource(CamelModel):
    template: str


@router.get("/naming", response_model=NamingTemplateResource)
async def get_naming_template(config=Depends(get_config)):
    return NamingTemplateResource(template=config.naming_template)


@router.post("/naming", response_model=NamingTemplateResource)
async def save_naming_template(
    body: NamingTemplateResource,
    config=Depends(get_config),
):
    config.naming_template = body.template
    config.save()
    return NamingTemplateResource(template=config.naming_template)


# ---------------------------------------------------------------------------
# Metadata settings
# ---------------------------------------------------------------------------


class MetadataSettingsResource(CamelModel):
    google_books_api_key: str
    internet_archive_enabled: bool
    annas_archive_enabled: bool
    annas_archive_mirror: str


class MetadataSettingsUpdateResource(CamelModel):
    google_books_api_key: str | None = None
    internet_archive_enabled: bool | None = None
    annas_archive_enabled: bool | None = None
    annas_archive_mirror: str | None = None


@router.get("/metadata", response_model=MetadataSettingsResource)
async def get_metadata_settings(config=Depends(get_config)):
    # Mask API key in response (show first 4 chars only if set)
    masked_key = ""
    if config.google_books_api_key:
        key = config.google_books_api_key
        if len(key) > 8:
            masked_key = key[:4] + "***" + key[-4:]
        else:
            masked_key = "***"

    return MetadataSettingsResource(
        google_books_api_key=masked_key,
        internet_archive_enabled=config.internet_archive_enabled,
        annas_archive_enabled=config.annas_archive_enabled,
        annas_archive_mirror=config.annas_archive_mirror,
    )


@router.post("/metadata", response_model=MetadataSettingsResource)
async def save_metadata_settings(
    body: MetadataSettingsUpdateResource,
    config=Depends(get_config),
):
    if body.google_books_api_key is not None:
        # Only update if it's a real new key (not a masked one)
        if "***" not in body.google_books_api_key:
            config.google_books_api_key = body.google_books_api_key
    if body.internet_archive_enabled is not None:
        config.internet_archive_enabled = body.internet_archive_enabled
    if body.annas_archive_enabled is not None:
        config.annas_archive_enabled = body.annas_archive_enabled
    if body.annas_archive_mirror is not None:
        config.annas_archive_mirror = body.annas_archive_mirror
    config.save()

    masked_key = ""
    if config.google_books_api_key:
        key = config.google_books_api_key
        if len(key) > 8:
            masked_key = key[:4] + "***" + key[-4:]
        else:
            masked_key = "***"

    return MetadataSettingsResource(
        google_books_api_key=masked_key,
        internet_archive_enabled=config.internet_archive_enabled,
        annas_archive_enabled=config.annas_archive_enabled,
        annas_archive_mirror=config.annas_archive_mirror,
    )


# ---------------------------------------------------------------------------
# Metadata tests
# ---------------------------------------------------------------------------


class GoogleBooksTestRequest(CamelModel):
    api_key: str


@router.post("/metadata/test/googlebooks", response_model=TestResult)
async def test_google_books(body: GoogleBooksTestRequest):
    """Test Google Books API connectivity with the provided key."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={
                    "q": "intitle:magazine",
                    "printType": "magazines",
                    "maxResults": 1,
                    "key": body.api_key,
                },
            )
            if resp.status_code == 200:
                return TestResult(is_valid=True, message="Google Books connection successful")
            return TestResult(
                is_valid=False,
                message=f"Google Books returned status {resp.status_code}",
            )
    except Exception as e:
        return TestResult(is_valid=False, message=str(e))


@router.post("/metadata/test/internetarchive", response_model=TestResult)
async def test_internet_archive():
    """Test Internet Archive connectivity."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://archive.org/metadata/test")
            if resp.status_code == 200:
                return TestResult(
                    is_valid=True,
                    message="Internet Archive connection successful",
                )
            return TestResult(
                is_valid=False,
                message=f"Internet Archive returned status {resp.status_code}",
            )
    except Exception as e:
        return TestResult(is_valid=False, message=str(e))


class AnnasArchiveTestRequest(CamelModel):
    mirror: str = "annas-archive.li"


@router.post("/metadata/test/annasarchive", response_model=TestResult)
async def test_annas_archive(body: AnnasArchiveTestRequest):
    """Test Anna's Archive connectivity with the provided mirror URL."""
    from app.metadata.annas_archive import AnnasArchiveProvider

    provider = AnnasArchiveProvider(mirror=body.mirror)
    try:
        ok, message = await provider.test_connection()
        return TestResult(is_valid=ok, message=message)
    except Exception as e:
        return TestResult(is_valid=False, message=str(e))
    finally:
        await provider.close()
