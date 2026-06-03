"""JDownloader 2 folder-watch dispatcher.

Sends a ``MagazineRelease`` to a JD2 instance by writing a
``.crawljob`` file into the operator-configured "folder watch"
directory. JD2's Folder Watch extension picks the file up,
adds the URLs to LinkGrabber, auto-starts the download and
files the result into the configured destination.

Why folder-watch and not the JD2 HTTP API?
- The HTTP API ("Direct Connection") is half-supported, often
  disabled by default on fresh installs, and the auth flow
  (My JDownloader credentials, even when using the local
  device) is brittle.
- Folder Watch is a built-in JD2 extension, plaintext format,
  no auth, no service to expose. Pressarr writes one file ->
  done.

Crawljob format (one ``key=value`` per line, blank line between
jobs — we emit one job per release):

  text=<\n-joined hoster urls>
  filename=<release id + sanitised title>
  packageName=<magazine title>
  downloadFolder=<JD2 output path>
  autoConfirm=TRUE
  autoStart=TRUE
  forcedStart=TRUE
  enabled=TRUE
  overwritePackagizerEnabled=TRUE
  extractAfterDownload=FALSE
  comment=pressarr:release=<id>

The ``comment`` field gives us a way to correlate a download
back to the release row in the future status-polling pass.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from app.models.magazine import Magazine
from app.models.magazine_release import MagazineRelease

logger = logging.getLogger(__name__)


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class JDownloaderDispatchError(RuntimeError):
    """Raised when the dispatcher can't write the .crawljob —
    folderwatch path missing, not writable, no hosters on the
    release, etc. Caller surfaces this to the operator."""


def _slug(value: str, max_len: int = 80) -> str:
    """Filename-safe version of a release title. Collapses
    runs of non-[A-Za-z0-9._-] into single dashes and clamps
    length to keep the resulting ``.crawljob`` filename short
    enough for every filesystem on the planet."""
    s = (value or "release").strip()
    s = _SAFE_FILENAME_RE.sub("-", s).strip("-_.")
    return (s or "release")[:max_len]


def _hoster_urls(release: MagazineRelease) -> list[str]:
    try:
        data = json.loads(release.hoster_links or "[]")
    except Exception:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for entry in data:
        url = (entry or {}).get("url")
        if isinstance(url, str) and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _build_crawljob(
    *,
    release: MagazineRelease,
    magazine_title: str,
    output_path: str,
    urls: list[str],
) -> str:
    """Render the JD2 crawljob payload. JD2 reads it line-by-
    line; ``\\n`` separators inside ``text=`` are the convention
    for multi-URL jobs."""
    text_urls = "\n".join(urls)
    package_name = magazine_title or release.title or "magazine"
    filename = _slug(
        f"{release.id}-{release.issue_label or release.title}"
    )
    lines = [
        f"text={text_urls}",
        f"filename={filename}",
        f"packageName={package_name}",
        f"downloadFolder={output_path}",
        "autoConfirm=TRUE",
        "autoStart=TRUE",
        "forcedStart=TRUE",
        "enabled=TRUE",
        "overwritePackagizerEnabled=TRUE",
        "extractAfterDownload=FALSE",
        f"comment=pressarr:release={release.id}",
    ]
    return "\n".join(lines) + "\n"


def dispatch_release(
    *,
    release: MagazineRelease,
    magazine: Magazine,
    config,
) -> Path:
    """Write the ``.crawljob`` file for ``release`` into the
    configured folder-watch directory. Returns the path of the
    file written. Mutates the release: ``status='grabbed'``,
    ``grabbed_at=<now>``, ``status_message`` set on the rare
    failure path. Caller still needs to commit the session."""

    if not getattr(config, "jdownloader_enabled", False):
        raise JDownloaderDispatchError(
            "JDownloader dispatcher is disabled in the pressarr config"
        )
    folderwatch = (config.jdownloader_folderwatch or "").strip()
    if not folderwatch:
        raise JDownloaderDispatchError(
            "jdownloader_folderwatch is not configured"
        )
    output_path = (config.jdownloader_output_path or "").strip()
    if not output_path:
        raise JDownloaderDispatchError(
            "jdownloader_output_path is not configured"
        )

    urls = _hoster_urls(release)
    if not urls:
        raise JDownloaderDispatchError(
            "Release has no hoster URLs to dispatch"
        )

    folder = Path(folderwatch)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise JDownloaderDispatchError(
            f"Could not create folder-watch directory {folder}: {e!s}"
        ) from e

    payload = _build_crawljob(
        release=release,
        magazine_title=magazine.title,
        output_path=output_path,
        urls=urls,
    )
    crawljob_path = folder / f"{_slug(magazine.title)}-{release.id}.crawljob"
    try:
        crawljob_path.write_text(payload, encoding="utf-8")
    except OSError as e:
        raise JDownloaderDispatchError(
            f"Could not write {crawljob_path}: {e!s}"
        ) from e

    release.status = "grabbed"
    release.grabbed_at = datetime.utcnow()
    release.status_message = (
        f"Dispatched to JDownloader 2 via {crawljob_path.name}"
    )

    logger.info(
        "Dispatched release id=%s magazine=%r to JD2 (%s, %d url(s))",
        release.id, magazine.title, crawljob_path, len(urls),
    )
    return crawljob_path
