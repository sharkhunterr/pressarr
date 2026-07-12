"""Async FlareSolverr client.

Mirrors the small subset of the FlareSolverr v1 API that
pressarr's scene scrapers need:

- ``sessions.create`` / ``sessions.destroy`` — one persistent
  Chromium tab per indexer so a login (POST) and the
  following searches (GET) share cookies.
- ``request.get`` and ``request.post`` — issue an HTTP request
  *inside* the headless Chromium that FlareSolverr controls.
  The response includes both the final rendered HTML (after
  the CHEQ / Cloudflare JS challenge runs) AND the cookie jar
  the page accumulated.

Sidecar URL defaults to ``http://flaresolverr:8191/v1``, same
as grabarr's docker-compose so a single FlareSolverr container
can serve both apps.

We use httpx (async) here even though the FlareSolverr request
itself is synchronous-ish — keeps the calling scrapers fully
async and avoids dragging in ``requests``.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FlareSolverrError(RuntimeError):
    """Raised when the bypass call fails or the sidecar reports
    a non-``ok`` status. Scrapers usually catch this and fall
    back to "no releases" rather than propagating an exception
    through the API."""


class FlareSolverrClient:
    """Thin async wrapper around the FlareSolverr v1 API."""

    def __init__(self, base_url: str, timeout_ms: int = 60_000):
        self.base_url = base_url.rstrip("/")
        self.timeout_ms = timeout_ms
        # Read timeout = solver budget + small slack. Connect
        # timeout stays tight so a missing sidecar fails fast.
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=8.0,
                read=(timeout_ms / 1000.0) + 15.0,
                write=8.0,
                pool=None,
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    async def create_session(self, name: str) -> str:
        """Spin up a fresh Chromium tab. Returns the session id
        (same as ``name`` when accepted). Idempotent: if a
        session of that name already exists FlareSolverr just
        returns it without complaint."""
        try:
            payload = await self._call(
                {"cmd": "sessions.create", "session": name}
            )
            return payload.get("session", name)
        except FlareSolverrError as e:
            logger.warning(
                "FlareSolverr session.create failed for %r: %s", name, e
            )
            raise

    async def destroy_session(self, name: str) -> None:
        try:
            await self._call(
                {"cmd": "sessions.destroy", "session": name}
            )
        except FlareSolverrError:
            # destroy is best-effort — the sidecar GC's stale
            # sessions on its own anyway.
            pass

    # ------------------------------------------------------------------
    # HTTP-through-Chromium
    # ------------------------------------------------------------------
    async def request_get(
        self, url: str, session: str | None = None
    ) -> dict[str, Any]:
        """GET ``url`` through the sidecar. Returns the
        ``solution`` payload — keys you'll likely use:

        - ``url``: final URL after redirects
        - ``status``: HTTP status code from the target
        - ``response``: full rendered HTML
        - ``cookies``: list of ``{name, value, ...}`` dicts
        """
        body: dict[str, Any] = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": self.timeout_ms,
        }
        if session:
            body["session"] = session
        payload = await self._call(body)
        return payload.get("solution") or {}

    async def request_post(
        self,
        url: str,
        post_data: str,
        session: str | None = None,
    ) -> dict[str, Any]:
        """POST ``post_data`` (already URL-encoded — the
        FlareSolverr docs are strict on this) to ``url`` through
        the sidecar. Same return shape as ``request_get``."""
        body: dict[str, Any] = {
            "cmd": "request.post",
            "url": url,
            "postData": post_data,
            "maxTimeout": self.timeout_ms,
        }
        if session:
            body["session"] = session
        payload = await self._call(body)
        return payload.get("solution") or {}

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------
    async def _call(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = await self._client.post(
                self.base_url,
                json=body,
                headers={"Content-Type": "application/json"},
            )
        except httpx.RequestError as e:
            raise FlareSolverrError(
                f"FlareSolverr unreachable at {self.base_url}: {e!s}"
            ) from e
        try:
            data = resp.json()
        except Exception as e:
            raise FlareSolverrError(
                f"FlareSolverr returned non-JSON ({resp.status_code})"
            ) from e
        status = data.get("status")
        if status != "ok":
            raise FlareSolverrError(
                f"FlareSolverr cmd={body.get('cmd')} returned "
                f"status={status!r} message={data.get('message')!r}"
            )
        return data


def build_client(config) -> FlareSolverrClient | None:
    """Construct a client from the live config. Returns ``None``
    when no endpoint is configured — callers treat that as "no
    bypass available" and skip the indexers that need it."""
    url = (getattr(config, "flaresolverr_url", "") or "").strip()
    if not url:
        return None
    return FlareSolverrClient(
        base_url=url,
        timeout_ms=getattr(config, "flaresolverr_timeout_ms", 60000),
    )
