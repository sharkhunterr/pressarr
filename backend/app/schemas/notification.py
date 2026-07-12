"""Notification Pydantic schemas."""

import json
from typing import Any

from pydantic import field_validator

from app.schemas import CamelModel

# Keys in notification settings that contain secrets
_SECRET_KEYS = {"webhook_url", "token", "app_token", "bot_token", "api_key", "password"}


def _mask_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Mask secret values in notification settings for API responses."""
    masked = {}
    for key, value in settings.items():
        if key in _SECRET_KEYS and isinstance(value, str) and len(value) > 8:
            masked[key] = value[:4] + "***" + value[-4:]
        else:
            masked[key] = value
    return masked


class NotificationResource(CamelModel):
    """Response schema for a notification."""

    id: int
    name: str
    notification_type: str
    settings: dict[str, Any]
    on_grab: bool
    on_download: bool
    on_import: bool
    on_upgrade: bool
    on_error: bool
    enabled: bool

    @field_validator("settings", mode="before")
    @classmethod
    def parse_settings(cls, v: Any) -> dict[str, Any]:
        if isinstance(v, str):
            v = json.loads(v)
        return _mask_settings(v)


class NotificationCreateResource(CamelModel):
    """Request schema to create a notification."""

    name: str
    notification_type: str
    settings: dict[str, Any]
    on_grab: bool = True
    on_download: bool = True
    on_import: bool = True
    on_upgrade: bool = True
    on_error: bool = True
    enabled: bool = True

    def settings_json(self) -> str:
        """Serialize settings dict to JSON string for DB storage."""
        return json.dumps(self.settings)


class NotificationUpdateResource(CamelModel):
    """Request schema to update a notification."""

    name: str | None = None
    settings: dict[str, Any] | None = None
    on_grab: bool | None = None
    on_download: bool | None = None
    on_import: bool | None = None
    on_upgrade: bool | None = None
    on_error: bool | None = None
    enabled: bool | None = None

    def settings_json(self) -> str | None:
        """Serialize settings dict to JSON string for DB storage, or None."""
        if self.settings is None:
            return None
        return json.dumps(self.settings)


class NotificationTestResult(CamelModel):
    """Response schema for a notification test."""

    is_valid: bool
    message: str
