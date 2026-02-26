"""Search API endpoints."""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_config, get_db
from app.schemas import CamelModel
from app.schemas.search import GrabResponse, SearchResultResource
from app.services import search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


@router.get("", response_model=list[SearchResultResource])
async def search(
    issue_id: int | None = Query(None, alias="issueId"),
    magazine_id: int | None = Query(None, alias="magazineId"),
    query: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    if issue_id:
        return await search_service.search_issue(db, issue_id, config)
    elif magazine_id:
        results_by_issue = await search_service.search_magazine_missing(db, magazine_id, config)
        # Flatten all results
        all_results = []
        for issue_results in results_by_issue.values():
            all_results.extend(issue_results)
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results
    elif query:
        # Free search - not tied to a specific issue
        return []
    raise HTTPException(422, "Provide issueId, magazineId, or query")


@router.post("/grab", response_model=GrabResponse)
async def grab_release(
    body: dict,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    issue_id = body.get("issueId")
    download_url = body.get("downloadUrl")
    title = body.get("title", "")
    protocol = body.get("protocol", "torrent")
    guid = body.get("guid", "")

    if not issue_id or not download_url:
        raise HTTPException(422, "issueId and downloadUrl are required")

    from app.services.download_service import grab_release as do_grab
    result = await do_grab(db, issue_id, download_url, title, protocol, guid)
    return result


# ---- Internet Archive endpoints ----------------------------------------


@router.get("/internetarchive", response_model=list[SearchResultResource])
async def search_internet_archive(
    query: str = Query(...),
    magazine_id: int | None = Query(None, alias="magazineId"),
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Search the Internet Archive for magazine issues."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {
                "q": f'collection:magazine_rack "{query}"',
                "fl[]": ["identifier", "title", "date", "format", "downloads"],
                "rows": 50,
                "output": "json",
            }
            resp = await client.get(
                "https://archive.org/advancedsearch.php", params=params
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("IA search failed: %s", e)
        raise HTTPException(502, f"Internet Archive search failed: {e}")

    docs = data.get("response", {}).get("docs", [])

    results: list[SearchResultResource] = []
    for doc in docs:
        identifier = doc.get("identifier", "")
        title = doc.get("title", identifier)
        formats = doc.get("format", [])
        if isinstance(formats, str):
            formats = [formats]

        results.append(SearchResultResource(
            guid=identifier,
            title=title,
            indexer="Internet Archive",
            size=0,
            age=0,
            protocol="ia",
            seeders=doc.get("downloads"),
            quality="unknown",
            language="unknown",
            score=0.0,
            is_blocklisted=False,
            download_url=f"https://archive.org/download/{identifier}",
        ))

    # If magazine_id is provided, run matching logic
    if magazine_id and results:
        from app.services.search_service import match_ia_results
        results = await match_ia_results(db, results, magazine_id)

    return results


class IADownloadRequest(CamelModel):
    identifier: str
    filename: str = ""
    issue_id: int | None = None
    preferred_format: str = "pdf"


# Priority order for downloadable formats
_FORMAT_PRIORITY = [".pdf", ".cbz", ".cbr", ".epub"]


async def _resolve_ia_filename(identifier: str, preferred_format: str = "pdf") -> str:
    """Fetch IA item metadata and find the best downloadable file.

    The filename provided by the frontend is typically wrong (it just
    appends '.pdf' to the identifier). We need to look up the actual
    files inside the item and pick the best one.
    """
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"https://archive.org/metadata/{identifier}/files")
        resp.raise_for_status()
        files = resp.json().get("result", [])

    # Build a dict of extension -> best filename (largest file wins for ties)
    candidates: dict[str, tuple[str, int]] = {}
    for f in files:
        name = f.get("name", "")
        lower = name.lower()
        size = int(f.get("size", 0) or 0)
        for ext in _FORMAT_PRIORITY:
            if lower.endswith(ext):
                if ext not in candidates or size > candidates[ext][1]:
                    candidates[ext] = (name, size)
                break

    if not candidates:
        raise ValueError(f"No downloadable file found in IA item '{identifier}'")

    # Pick by priority, favouring preferred_format
    preferred_ext = f".{preferred_format.lstrip('.')}"
    if preferred_ext in candidates:
        return candidates[preferred_ext][0]
    for ext in _FORMAT_PRIORITY:
        if ext in candidates:
            return candidates[ext][0]

    # Shouldn't reach here given the check above
    raise ValueError(f"No downloadable file found in IA item '{identifier}'")


@router.post("/internetarchive/download", response_model=GrabResponse)
async def download_from_internet_archive(
    body: IADownloadRequest,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_config),
):
    """Download a specific file from the Internet Archive.

    The filename is auto-resolved from the item metadata so the caller
    only needs to provide the identifier.
    """
    from app.download_clients.internet_archive import InternetArchiveClient
    from app.services.history_service import create_event

    if not body.identifier:
        raise HTTPException(422, "identifier is required")

    # Auto-resolve the actual filename from IA metadata
    try:
        filename = await _resolve_ia_filename(
            body.identifier, body.preferred_format
        )
    except Exception as e:
        logger.error("Could not resolve IA filename for %s: %s", body.identifier, e)
        raise HTTPException(
            502, f"Could not find a downloadable file in IA item '{body.identifier}': {e}"
        )

    ia_client = InternetArchiveClient()
    try:
        download_dir = str(
            Path(getattr(config, "download_path", "/tmp/pressarr_downloads"))
            / "ia"
        )
        local_path = await ia_client.download(
            body.identifier, filename, download_dir
        )

        # If an issue_id is provided, trigger import
        if body.issue_id:
            from app.services.import_service import process_downloaded_file

            result = await process_downloaded_file(
                db, Path(local_path), config
            )
            if result.get("success"):
                await create_event(
                    db,
                    event_type="grab",
                    issue_id=body.issue_id,
                    details=f"Downloaded from IA: {body.identifier}/{filename}",
                )

        return GrabResponse(
            issue_id=body.issue_id or 0,
            download_id=f"{body.identifier}/{filename}",
            message=f"Downloaded to {local_path}",
        )
    except Exception as e:
        logger.error("IA download failed: %s", e, exc_info=True)
        raise HTTPException(502, f"Internet Archive download failed: {e}")
    finally:
        await ia_client.close()
