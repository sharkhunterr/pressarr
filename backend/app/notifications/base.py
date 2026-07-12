"""Abstract notification provider base class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotificationPayload:
    """Payload for a notification event."""

    event_type: str  # grab, download, import, upgrade, error
    magazine_title: str
    issue_number: int | None = None
    issue_title: str | None = None
    quality: str | None = None
    cover_url: str | None = None
    message: str | None = None


class NotificationProvider(ABC):
    """Base class for all notification providers."""

    def __init__(self, settings: dict) -> None:
        self.settings = settings

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> None:
        """Send a notification for the given payload."""
        ...

    @abstractmethod
    async def test(self) -> tuple[bool, str]:
        """Send a test notification. Returns (success, message)."""
        ...

    def format_title(self, payload: NotificationPayload) -> str:
        """Format a human-readable title from the payload."""
        parts = ["Pressarr"]
        if payload.event_type == "grab":
            parts.append("Grabbed")
        elif payload.event_type == "import":
            parts.append("Imported")
        elif payload.event_type == "upgrade":
            parts.append("Upgraded")
        elif payload.event_type == "error":
            parts.append("Error")
        else:
            parts.append(payload.event_type.capitalize())
        return " - ".join(parts)

    def format_body(self, payload: NotificationPayload) -> str:
        """Format a human-readable body from the payload."""
        lines = [payload.magazine_title]
        if payload.issue_number is not None:
            lines[0] += f" #{payload.issue_number}"
        if payload.quality and payload.quality != "unknown":
            lines.append(f"Quality: {payload.quality}")
        if payload.message:
            lines.append(payload.message)
        return "\n".join(lines)
