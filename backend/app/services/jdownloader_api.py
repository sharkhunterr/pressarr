"""Async client for JDownloader 2's local API.

JD2 serves its API without a MyJDownloader account when the
"deprecated API" is on (Settings > Advanced > ``RemoteAPI``:
``DeprecatedApiEnabled``, port 3128; ``DeprecatedApiLocalhostOnly``
off when pressarr runs in another container). Each call is a GET
whose parameters are JSON values in the query string:
``/downloadsV2/queryLinks?{"bytesLoaded":true}``.
"""

import json
import logging
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_LINK_FIELDS = {
    "bytesLoaded": True,
    "bytesTotal": True,
    "comment": True,
    "enabled": True,
    "eta": True,
    "finished": True,
    "host": True,
    "packageUUID": True,
    "running": True,
    "skipped": True,
    "speed": True,
    "status": True,
}


class JDownloaderApiError(RuntimeError):
    """JD2 could not be reached or refused the call."""


class JDownloaderApi:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(self, path: str, *params: Any) -> Any:
        url = f"{self.base_url}/{path}"
        if params:
            url += "?" + "&".join(quote(json.dumps(p)) for p in params)
        try:
            resp = await self._client.get(url)
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise JDownloaderApiError(f"JDownloader API unreachable: {e!s}") from e
        if resp.status_code != 200 or "type" in data:
            raise JDownloaderApiError(
                f"JDownloader API {path} answered {resp.status_code}: {data}"
            )
        return data.get("data")

    async def download_links(self) -> list[dict]:
        return await self._call("downloadsV2/queryLinks", _LINK_FIELDS) or []

    async def download_packages(self) -> list[dict]:
        return await self._call("downloadsV2/queryPackages", {"saveTo": True}) or []

    async def linkgrabber_links(self) -> list[dict]:
        """Links JD2 is still checking, or could not add to its
        download list (``availability``: ONLINE, OFFLINE, UNKNOWN)."""
        return (
            await self._call(
                "linkgrabberv2/queryLinks",
                {"availability": True, "comment": True, "host": True},
            )
            or []
        )

    async def remove_download_links(self, link_ids: list[int]) -> None:
        await self._call("downloadsV2/removeLinks", link_ids, [])

    async def remove_linkgrabber_links(self, link_ids: list[int]) -> None:
        await self._call("linkgrabberv2/removeLinks", link_ids, [])
