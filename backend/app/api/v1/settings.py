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
    import_mode: str


class GeneralSettingsUpdateResource(CamelModel):
    port: int | None = None
    log_level: str | None = None
    auth_enabled: bool | None = None
    scheduled_task_interval: int | None = None
    import_mode: str | None = None


@router.get("/general", response_model=GeneralSettingsResource)
async def get_general_settings(config=Depends(get_config)):
    return GeneralSettingsResource(
        port=config.port,
        log_level=config.log_level,
        auth_enabled=config.auth_enabled,
        scheduled_task_interval=config.rss_sync_interval // 60,
        import_mode=config.import_mode,
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
    if body.import_mode is not None and body.import_mode in ("copy", "move", "copy_delete"):
        config.import_mode = body.import_mode
    config.save()

    return GeneralSettingsResource(
        port=config.port,
        log_level=config.log_level,
        auth_enabled=config.auth_enabled,
        scheduled_task_interval=config.rss_sync_interval // 60,
        import_mode=config.import_mode,
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


# ---------------------------------------------------------------------------
# Scene magazine indexers (Bookys, telecharger-magazines.org)
# + JDownloader 2 dispatcher + FlareSolverr bypass endpoint.
# Bundled in one resource because the UI surfaces them on a
# single page — the operator typically configures them
# together (Bookys needs FlareSolverr, JD2 needs an output
# path the importer can poll).
# ---------------------------------------------------------------------------


class _CredsMask:
    """Helper — never echo passwords / sensitive strings back
    in the GET response, but accept the same shape on PUT so
    the UI doesn't have to be aware of masking."""

    PLACEHOLDER = "***"

    @staticmethod
    def mask(value: str | None) -> str:
        return _CredsMask.PLACEHOLDER if value else ""

    @staticmethod
    def keep(incoming: str | None, current: str) -> str:
        # ``None`` from a partial PUT = "don't touch"; the
        # placeholder also means "keep current"; everything
        # else (even empty string) replaces.
        if incoming is None or incoming == _CredsMask.PLACEHOLDER:
            return current
        return incoming


class SceneIndexersResource(CamelModel):
    bookys_enabled: bool
    bookys_url: str
    bookys_username: str
    bookys_password: str
    telecharger_magazines_enabled: bool
    telecharger_magazines_url: str
    flaresolverr_url: str
    flaresolverr_timeout_ms: int
    jdownloader_enabled: bool
    jdownloader_folderwatch: str
    jdownloader_output_path: str


class SceneIndexersUpdateResource(CamelModel):
    bookys_enabled: bool | None = None
    bookys_url: str | None = None
    bookys_username: str | None = None
    bookys_password: str | None = None
    telecharger_magazines_enabled: bool | None = None
    telecharger_magazines_url: str | None = None
    flaresolverr_url: str | None = None
    flaresolverr_timeout_ms: int | None = None
    jdownloader_enabled: bool | None = None
    jdownloader_folderwatch: str | None = None
    jdownloader_output_path: str | None = None


def _serialise_scene_indexers(config) -> SceneIndexersResource:
    return SceneIndexersResource(
        bookys_enabled=config.bookys_enabled,
        bookys_url=config.bookys_url,
        bookys_username=config.bookys_username,
        bookys_password=_CredsMask.mask(config.bookys_password),
        telecharger_magazines_enabled=config.telecharger_magazines_enabled,
        telecharger_magazines_url=config.telecharger_magazines_url,
        flaresolverr_url=config.flaresolverr_url,
        flaresolverr_timeout_ms=config.flaresolverr_timeout_ms,
        jdownloader_enabled=config.jdownloader_enabled,
        jdownloader_folderwatch=config.jdownloader_folderwatch,
        jdownloader_output_path=config.jdownloader_output_path,
    )


@router.get("/scene-indexers", response_model=SceneIndexersResource)
async def get_scene_indexers(config=Depends(get_config)):
    return _serialise_scene_indexers(config)


@router.post("/scene-indexers", response_model=SceneIndexersResource)
async def save_scene_indexers(
    body: SceneIndexersUpdateResource,
    config=Depends(get_config),
):
    if body.bookys_enabled is not None:
        config.bookys_enabled = body.bookys_enabled
    if body.bookys_url is not None:
        config.bookys_url = body.bookys_url.rstrip("/")
    if body.bookys_username is not None:
        config.bookys_username = body.bookys_username
    # Password is masked on GET → use the keep helper so the
    # placeholder coming back unchanged doesn't wipe the stored
    # value.
    config.bookys_password = _CredsMask.keep(
        body.bookys_password, config.bookys_password
    )
    if body.telecharger_magazines_enabled is not None:
        config.telecharger_magazines_enabled = (
            body.telecharger_magazines_enabled
        )
    if body.telecharger_magazines_url is not None:
        config.telecharger_magazines_url = (
            body.telecharger_magazines_url.rstrip("/")
        )
    if body.flaresolverr_url is not None:
        config.flaresolverr_url = body.flaresolverr_url
    if body.flaresolverr_timeout_ms is not None:
        config.flaresolverr_timeout_ms = body.flaresolverr_timeout_ms
    if body.jdownloader_enabled is not None:
        config.jdownloader_enabled = body.jdownloader_enabled
    if body.jdownloader_folderwatch is not None:
        config.jdownloader_folderwatch = body.jdownloader_folderwatch
    if body.jdownloader_output_path is not None:
        config.jdownloader_output_path = body.jdownloader_output_path
    config.save()
    return _serialise_scene_indexers(config)


@router.post("/scene-indexers/test/bookys", response_model=TestResult)
async def test_bookys(config=Depends(get_config)):
    """Exercise the configured Bookys credentials through the
    configured FlareSolverr endpoint. Returns ``is_valid=True``
    only when the login dance reaches the ``dle_user_id``
    cookie — anything before that surfaces with the failure
    reason so the operator knows whether it's a CF/JS issue,
    a wrong-creds issue, or a sidecar issue."""
    from app.indexers.magazine_scene.bookys import BookysIndexer
    from app.services.flaresolverr import build_client

    flare = build_client(config)
    indexer = BookysIndexer(
        base_url=config.bookys_url,
        username=config.bookys_username,
        password=config.bookys_password,
        flaresolverr=flare,
    )
    try:
        ok, message = await indexer.test_connection()
        return TestResult(is_valid=ok, message=message)
    except Exception as e:
        return TestResult(is_valid=False, message=str(e))
    finally:
        await indexer.close()


@router.post(
    "/scene-indexers/test/telecharger-magazines",
    response_model=TestResult,
)
async def test_telecharger_magazines(config=Depends(get_config)):
    """Reach the tm.org homepage to confirm the URL is alive
    and not behind a 5xx. No login = nothing more to verify."""
    from app.indexers.magazine_scene.telecharger_magazines import (
        TelechargerMagazinesIndexer,
    )

    indexer = TelechargerMagazinesIndexer(
        base_url=config.telecharger_magazines_url
    )
    try:
        ok, message = await indexer.test_connection()
        return TestResult(is_valid=ok, message=message)
    except Exception as e:
        return TestResult(is_valid=False, message=str(e))
    finally:
        await indexer.close()


@router.post(
    "/scene-indexers/test/flaresolverr",
    response_model=TestResult,
)
async def test_flaresolverr(config=Depends(get_config)):
    """Hit the FlareSolverr sidecar with a tiny ``request.get``
    against ``example.com`` so the operator can confirm the
    endpoint URL is correct before turning Bookys on."""
    from app.services.flaresolverr import (
        FlareSolverrError,
        build_client,
    )

    client = build_client(config)
    if client is None:
        return TestResult(
            is_valid=False, message="FlareSolverr URL is not configured"
        )
    try:
        sol = await client.request_get("https://example.com")
        if (sol or {}).get("status") == 200:
            return TestResult(
                is_valid=True,
                message=(
                    "FlareSolverr reached the test target "
                    "(example.com)"
                ),
            )
        return TestResult(
            is_valid=False,
            message=(
                f"FlareSolverr reached but example.com returned "
                f"status={(sol or {}).get('status')}"
            ),
        )
    except FlareSolverrError as e:
        return TestResult(is_valid=False, message=str(e))
    except Exception as e:
        return TestResult(is_valid=False, message=str(e))
    finally:
        await client.close()
