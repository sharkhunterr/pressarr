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
        """Add a torrent by URL. Returns the torrent's info-hash.

        qBittorrent's ``/torrents/add`` endpoint never returns the hash —
        il répond juste ``200 Ok.``. On a besoin du hash pour que le
        monitor puisse poller ``/torrents/info?hashes=<id>`` plus tard ;
        passer l'URL source comme id (l'ancien fallback) fait rater
        chaque poll car le filtre qBit ne matche que les vrais hashes.

        Deux cas à couvrir :
          - torrent JAMAIS vu → snapshot "before" ne le contient pas,
            après add il apparaît → diff nous donne le nouveau hash.
          - torrent DÉJÀ présent (re-grab du même release) → diff vide
            car qBit ne dédoublonne pas. Dans ce cas on prend le torrent
            de la catégorie dont ``added_on`` est le plus récent — c'est
            très probablement celui qui vient d'être re-touché.

        Sans ce cas #2, un re-grab du même magazine renvoyait l'URL
        comme "download_id" → grab_registry pollué → pack_dispatch
        jamais déclenché car impossible de retrouver l'entry registry
        depuis le hash réel remonté par get_all().
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
            # Snapshot best-effort — un hiccup ne doit pas bloquer l'add.
            pass

        resp = await self._client.post(
            f"{self.base_url}/api/v2/torrents/add",
            data={"urls": url, "category": category},
        )
        resp.raise_for_status()

        # Poll : cherche un nouveau hash, ou un torrent dont added_on
        # est très récent (re-add du même torrent).
        import time as _time
        window_start = _time.time() - 3  # 3 s de marge avant l'add

        last_current: list[dict] = []
        for _ in range(20):
            await asyncio.sleep(0.3)
            try:
                poll = await self._client.get(
                    f"{self.base_url}/api/v2/torrents/info",
                    params={"category": category},
                )
                poll.raise_for_status()
                current = poll.json()
                last_current = current
            except Exception:
                continue

            # Cas 1 : nouveau hash → c'est notre torrent
            new_hashes = [
                t.get("hash", "")
                for t in current
                if t.get("hash") and t["hash"] not in before
            ]
            if new_hashes:
                new_hashes.sort(
                    key=lambda h: next(
                        (t.get("added_on", 0) for t in current if t.get("hash") == h),
                        0,
                    ),
                    reverse=True,
                )
                return new_hashes[0]

            # Cas 2 : pas de nouveau hash mais un torrent existant a été
            # touché récemment (added_on > window_start) → re-add
            recently_touched = [
                (t.get("hash", ""), t.get("added_on", 0))
                for t in current
                if t.get("hash") and (t.get("added_on") or 0) >= window_start
            ]
            if recently_touched:
                recently_touched.sort(key=lambda p: p[1], reverse=True)
                return recently_touched[0][0]

        # Ultime fallback : le torrent de la catégorie avec added_on le
        # plus récent (mieux qu'une URL fake qui pollue le registry).
        if last_current:
            latest = max(
                (t for t in last_current if t.get("hash")),
                key=lambda t: t.get("added_on", 0),
                default=None,
            )
            if latest:
                return latest["hash"]

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
