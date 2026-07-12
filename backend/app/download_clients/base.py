"""Abstract base class for download client integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DownloadStatus:
    """Status of a single download."""

    download_id: str
    name: str
    status: str  # downloading, completed, failed, paused
    progress: float  # 0.0 to 1.0
    size: int  # bytes
    speed: int  # bytes/sec
    eta: int  # seconds remaining
    save_path: str | None = None


class DownloadClientBase(ABC):
    """Abstract base for all download clients."""

    @abstractmethod
    async def add_torrent(self, url: str, category: str = "pressarr") -> str: ...

    @abstractmethod
    async def add_nzb(self, url: str, category: str = "pressarr") -> str: ...

    @abstractmethod
    async def get_status(self, download_id: str) -> DownloadStatus | None: ...

    @abstractmethod
    async def get_all(self, category: str = "pressarr") -> list[DownloadStatus]: ...

    @abstractmethod
    async def remove(
        self, download_id: str, delete_data: bool = False
    ) -> bool: ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]: ...
