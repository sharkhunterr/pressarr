"""Shared shape for scene magazine indexers.

Two providers ship today (Bookys, telecharger-magazines.org).
Both scrape HTML and return zero-to-many releases per query.
Each release lists at least one file-hoster link (1fichier,
Uploaded, Nitroflare, RapidGator, …) that the configured
download client (JDownloader 2 folder-watch in the v1
implementation) will resolve and fetch.

Concrete subclasses live next to this file (``bookys.py``,
``telecharger_magazines.py``).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class HosterLink:
    """One link inside a scene release. ``hoster`` is the host's
    bare domain (``1fichier.com``, ``uploaded.net``); ``url`` is
    the full download URL."""

    hoster: str
    url: str


@dataclass
class MagazineSceneRelease:
    """One scraped magazine release ready to be persisted as a
    ``MagazineRelease`` row. Free-form ``title`` is kept as-is
    for display; ``issue_label`` / ``year`` / ``language`` are
    best-effort parses of the title or page-side metadata.
    """

    source: str
    source_url: str
    title: str
    hoster_links: list[HosterLink] = field(default_factory=list)
    issue_label: str | None = None
    year: int | None = None
    language: str | None = None
    file_format: str | None = None
    size_bytes: int | None = None
    published_at: str | None = None
    cover_url: str | None = None


class MagazineSceneIndexerBase(ABC):
    """Minimum surface every scene magazine indexer exposes."""

    name: str  # short slug stored on the MagazineRelease row

    @abstractmethod
    async def search(self, query: str) -> list[MagazineSceneRelease]:
        """Return zero-to-many releases matching ``query``. A
        release without ``hoster_links`` is dropped by the caller
        rather than persisted."""

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """``(ok, message)``. Used by the settings page to give
        operators a one-click sanity check (Bookys is especially
        prone to login regressions when the site CSRF token
        moves)."""
