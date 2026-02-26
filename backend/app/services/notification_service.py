"""Notification service — CRUD and dispatching."""

import json
import logging
from importlib import import_module

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.notifications.base import NotificationPayload, NotificationProvider
from app.schemas.notification import NotificationCreateResource, NotificationUpdateResource

logger = logging.getLogger(__name__)

PROVIDERS: dict[str, str] = {
    "discord": "app.notifications.discord.DiscordProvider",
    "gotify": "app.notifications.gotify.GotifyProvider",
    "telegram": "app.notifications.telegram.TelegramProvider",
    "webhook": "app.notifications.webhook.WebhookProvider",
}


def _get_provider(notification: Notification) -> NotificationProvider:
    """Instantiate the correct provider for a notification record."""
    settings = (
        json.loads(notification.settings)
        if isinstance(notification.settings, str)
        else notification.settings
    )

    provider_path = PROVIDERS.get(notification.notification_type)
    if not provider_path:
        raise ValueError(f"Unknown notification type: {notification.notification_type}")

    module_path, class_name = provider_path.rsplit(".", 1)
    module = import_module(module_path)
    provider_cls: type[NotificationProvider] = getattr(module, class_name)
    return provider_cls(settings)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def dispatch(
    db: AsyncSession,
    event_type: str,
    payload: NotificationPayload,
) -> None:
    """Send notification to all enabled channels that have the event toggle on."""
    result = await db.execute(
        select(Notification).where(Notification.enabled == True)  # noqa: E712
    )
    notifications = result.scalars().all()

    for notif in notifications:
        toggle = getattr(notif, f"on_{event_type}", False)
        if not toggle:
            continue
        try:
            provider = _get_provider(notif)
            await provider.send(payload)
        except Exception:
            logger.warning(
                "Notification %s failed for event %s",
                notif.name,
                event_type,
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_notifications(db: AsyncSession) -> list[Notification]:
    """Return all notification records."""
    result = await db.execute(select(Notification))
    return list(result.scalars().all())


async def get_notification(db: AsyncSession, notif_id: int) -> Notification | None:
    """Return a single notification by ID, or None."""
    return await db.get(Notification, notif_id)


async def create_notification(
    db: AsyncSession,
    data: NotificationCreateResource,
) -> Notification:
    """Create and persist a new notification record."""
    notification = Notification(
        name=data.name,
        notification_type=data.notification_type,
        settings=data.settings_json(),
        on_grab=data.on_grab,
        on_download=data.on_download,
        on_import=data.on_import,
        on_upgrade=data.on_upgrade,
        on_error=data.on_error,
        enabled=data.enabled,
    )
    db.add(notification)
    await db.flush()
    await db.refresh(notification)
    return notification


async def update_notification(
    db: AsyncSession,
    notif_id: int,
    data: NotificationUpdateResource,
) -> Notification | None:
    """Update an existing notification. Returns None if not found."""
    notification = await db.get(Notification, notif_id)
    if notification is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "settings":
            setattr(notification, field, json.dumps(value))
        else:
            setattr(notification, field, value)

    await db.flush()
    await db.refresh(notification)
    return notification


async def delete_notification(db: AsyncSession, notif_id: int) -> bool:
    """Delete a notification by ID. Returns True if deleted, False if not found."""
    notification = await db.get(Notification, notif_id)
    if notification is None:
        return False
    await db.delete(notification)
    await db.flush()
    return True


async def test_notification(db: AsyncSession, notif_id: int) -> tuple[bool, str]:
    """Test a notification by ID. Returns (success, message)."""
    notification = await db.get(Notification, notif_id)
    if notification is None:
        return False, "Notification not found."
    try:
        provider = _get_provider(notification)
        return await provider.test()
    except Exception as exc:
        logger.warning("Test for notification %s failed", notification.name, exc_info=True)
        return False, f"Test failed: {exc}"
