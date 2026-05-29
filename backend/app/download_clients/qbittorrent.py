"""qBittorrent download client via REST API v2."""

import asyncio

import httpx

from app.download_clients.base import DownloadClientBase, DownloadStatus


class QBittorrentClient(DownloadClientBase):
    """Client for the qBittorrent Web API v2."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str = "admin",
        password: str = "",
        use_ssl: bool = False,
    ):
        scheme = "https" if use_ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}"
        self.username = username
        self.password = password
        self._client = httpx.AsyncClient(timeout=30.0)
        self._authenticated = False

    async def _login(self) -> None:
        """Authenticate via /api/v2/auth/login.

        qBittorrent returns ``200 Ok.`` on a successful credential
        check and ``200 Fails.`` on rejected creds. When the host
        has ``AuthSubnetWhitelist`` matching the caller's IP, qBit
        skips the auth check entirely and returns ``204 No
        Content`` with an empty body — that's the response shape
        for our LAN-shared instance. Treat any 2xx whose body is
        empty OR exactly ``Ok.`` as success; everything else is a
        real auth failure.
        """
        if self._authenticated:
            return
        resp = await self._client.post(
            f"{self.base_url}/api/v2/auth/login",
            data={"username": self.username, "password": self.password},
        )
        resp.raise_for_status()
        body = resp.text.strip().lower()
        if body and body != "ok.":
            raise RuntimeError(
                f"qBittorrent authentication failed: {body!r}"
            )
        self._authenticated = True

    async def add_torrent(self, url: str, category: str = "pressarr") -> str:
        """Add a torrent by URL. Returns the new torrent's info-hash.

        qBittorrent's ``/torrents/add`` endpoint never returns the hash —
        it just answers ``200 Ok.``. We need the hash so the monitor can
        poll ``/torrents/info?hashes=<id>`` later; passing the source URL
        as the id (the previous behaviour) made every poll miss because
        qBit's filter only matches actual info-hashes.

        Strategy: snapshot the hashes already present in ``category``
        before the add, fire the add, then poll the category until a new
        hash appears (or we give up after a few seconds). Diffing by
        category keeps the window small even on a busy client. If the
        diff never resolves we fall back to returning the URL so the
        caller still gets an identifier — the download will continue,
        only the status polling will be blind for that one item.
        """
        await self._login()

        before: set[str] = set()
        try:
            snap = await self._client.get(
                f"{self.base_url}/api/v2/torrents/info",
                params={"category": category},
            )
            snap.raise_for_status()
            before = {t.get("hash", "") for t in snap.json() if t.get("hash")}
        except Exception:
            # Snapshot is best-effort — a transient hiccup here
            # shouldn't block the actual add below.
            pass

        resp = await self._client.post(
            f"{self.base_url}/api/v2/torrents/add",
            data={"urls": url, "category": category},
        )
        resp.raise_for_status()

        # qBit registers the torrent asynchronously; poll briefly for it
        # to show up in the category. ~6 s total at 300 ms intervals is
        # well inside the importer's tolerance and long enough for the
        # metaDL stage of a fresh magnet/torrent fetch.
        for _ in range(20):
            await asyncio.sleep(0.3)
            try:
                poll = await self._client.get(
                    f"{self.base_url}/api/v2/torrents/info",
                    params={"category": category},
                )
                poll.raise_for_status()
                current = poll.json()
            except Exception:
                continue
            new_hashes = [
                t.get("hash", "")
                for t in current
                if t.get("hash") and t["hash"] not in before
            ]
            if new_hashes:
                # If multiple appeared (unlikely in 6 s), pick the most
                # recently added one — qBit sets ``added_on`` per torrent.
                new_hashes.sort(
                    key=lambda h: next(
                        (
                            t.get("added_on", 0)
                            for t in current
                            if t.get("hash") == h
                        ),
                        0,
                    ),
                    reverse=True,
                )
                return new_hashes[0]

        return url

    async def add_nzb(self, url: str, category: str = "pressarr") -> str:
        """qBittorrent does not support NZBs."""
        raise NotImplementedError("qBittorrent does not support NZB downloads")

    async def get_status(self, download_id: str) -> DownloadStatus | None:
        """Get status of a specific torrent by hash."""
        await self._login()
        resp = await self._client.get(
            f"{self.base_url}/api/v2/torrents/info",
            params={"hashes": download_id},
        )
        resp.raise_for_status()
        torrents = resp.json()
        if not torrents:
            return None
        return self._parse_torrent(torrents[0])

    async def get_all(self, category: str = "pressarr") -> list[DownloadStatus]:
        """Get all torrents, optionally filtered by category."""
        await self._login()
        resp = await self._client.get(
            f"{self.base_url}/api/v2/torrents/info",
            params={"category": category},
        )
        resp.raise_for_status()
        return [self._parse_torrent(t) for t in resp.json()]

    async def remove(
        self, download_id: str, delete_data: bool = False
    ) -> bool:
        """Remove a torrent by hash."""
        await self._login()
        resp = await self._client.post(
            f"{self.base_url}/api/v2/torrents/delete",
            data={
                "hashes": download_id,
                "deleteFiles": "true" if delete_data else "false",
            },
        )
        return resp.status_code == 200

    async def test_connection(self) -> tuple[bool, str]:
        """Test connection by logging in and retrieving the app version."""
        try:
            await self._login()
            resp = await self._client.get(
                f"{self.base_url}/api/v2/app/version"
            )
            resp.raise_for_status()
            version = resp.text.strip()
            return True, f"Connected to qBittorrent {version}"
        except Exception as e:
            return False, str(e)

    def _parse_torrent(self, data: dict) -> DownloadStatus:
        """Parse a qBittorrent torrent info dict into DownloadStatus."""
        # qBittorrent's ``state`` field is camelCase (``stalledUP``,
        # ``forcedDL``…). Compare case-insensitively so we don't silently
        # default everything to "downloading" — that was masking
        # ``stalledUP`` (= seeding, 100 % done), which kept finished
        # grabs out of the import path.
        state = data.get("state", "").lower()
        status_map = {
            "downloading": "downloading",
            "stalleddl": "downloading",
            "metadl": "downloading",
            "forceddl": "downloading",
            "uploading": "completed",
            "stalledup": "completed",
            "forcedup": "completed",
            "pauseddl": "paused",
            "pausedup": "completed",
            "queueddl": "downloading",
            "queuedup": "completed",
            "error": "failed",
            "missingfiles": "failed",
        }
        return DownloadStatus(
            download_id=data.get("hash", ""),
            name=data.get("name", ""),
            status=status_map.get(state, "downloading"),
            progress=data.get("progress", 0.0),
            size=data.get("total_size", 0),
            speed=data.get("dlspeed", 0),
            eta=data.get("eta", 0) or 0,
            save_path=data.get("save_path"),
        )

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
