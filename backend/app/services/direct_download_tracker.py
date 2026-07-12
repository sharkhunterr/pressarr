"""In-memory tracker for direct downloads (Internet Archive, Anna's Archive).

These downloads bypass torrent/usenet clients and stream files directly.
This module provides a global registry so the queue endpoint can include
them alongside regular downloads.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from app.download_clients.base import DownloadStatus

logger = logging.getLogger(__name__)


@dataclass
class TrackedDownload:
    """A tracked direct download with metadata for queue display."""

    status: DownloadStatus
    protocol: str  # "ia" or "aa"
    source: str  # "Internet Archive" or "Anna's Archive"
    issue_id: int | None = None
    magazine_id: int | None = None
    magazine_title: str | None = None
    issue_number: int | None = None
    error_message: str | None = None
    added: datetime = field(default_factory=datetime.now)
    task: asyncio.Task | None = field(default=None, repr=False)


class DirectDownloadTracker:
    """Singleton registry of active direct downloads."""

    def __init__(self) -> None:
        self._downloads: dict[str, TrackedDownload] = {}

    def register(
        self,
        download_id: str,
        name: str,
        protocol: str,
        source: str,
        issue_id: int | None = None,
        magazine_id: int | None = None,
        magazine_title: str | None = None,
        issue_number: int | None = None,
    ) -> TrackedDownload:
        """Register a new download. Returns the TrackedDownload."""
        status = DownloadStatus(
            download_id=download_id,
            name=name,
            status="queued",
            progress=0.0,
            size=0,
            speed=0,
            eta=0,
            save_path=None,
        )
        tracked = TrackedDownload(
            status=status,
            protocol=protocol,
            source=source,
            issue_id=issue_id,
            magazine_id=magazine_id,
            magazine_title=magazine_title,
            issue_number=issue_number,
        )
        self._downloads[download_id] = tracked
        logger.info("[tracker] Registered download %s (%s)", download_id, source)
        return tracked

    def get(self, download_id: str) -> TrackedDownload | None:
        return self._downloads.get(download_id)

    def get_all(self) -> list[TrackedDownload]:
        return list(self._downloads.values())

    def update_status(
        self,
        download_id: str,
        *,
        status: str | None = None,
        progress: float | None = None,
        size: int | None = None,
        speed: int | None = None,
        eta: int | None = None,
        name: str | None = None,
        save_path: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update fields on a tracked download."""
        tracked = self._downloads.get(download_id)
        if not tracked:
            return
        s = tracked.status
        if status is not None:
            s.status = status
        if progress is not None:
            s.progress = progress
        if size is not None:
            s.size = size
        if speed is not None:
            s.speed = speed
        if eta is not None:
            s.eta = eta
        if name is not None:
            s.name = name
        if save_path is not None:
            s.save_path = save_path
        if error_message is not None:
            tracked.error_message = error_message

    def remove(self, download_id: str) -> bool:
        """Remove a download from tracking. Cancels the task if running."""
        tracked = self._downloads.pop(download_id, None)
        if tracked:
            if tracked.task and not tracked.task.done():
                tracked.task.cancel()
            return True
        return False

    def cleanup_completed(self, max_age_seconds: int = 300) -> None:
        """Remove completed/failed/imported downloads older than their max age.

        "imported" items are cleaned up immediately (age 0) since the issue
        is already in the library, while "completed" and "failed" use the
        provided max_age_seconds.
        """
        now = datetime.now()
        to_remove = []
        for did, tracked in self._downloads.items():
            if tracked.status.status in ("completed", "failed", "imported"):
                age = (now - tracked.added).total_seconds()
                item_max_age = 0 if tracked.status.status == "imported" else max_age_seconds
                if age > item_max_age:
                    to_remove.append(did)
        for did in to_remove:
            del self._downloads[did]


# Global singleton
tracker = DirectDownloadTracker()
