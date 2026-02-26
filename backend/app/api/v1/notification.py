"""Notification API routes — /api/v1/notification."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.notification import (
    NotificationCreateResource,
    NotificationResource,
    NotificationTestResult,
    NotificationUpdateResource,
)
from app.services import notification_service

router = APIRouter(prefix="/api/v1/notification", tags=["Notifications"])


@router.get("", response_model=list[NotificationResource])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
) -> list[NotificationResource]:
    """List all notifications."""
    notifications = await notification_service.list_notifications(db)
    return [NotificationResource.model_validate(n) for n in notifications]


@router.post("", response_model=NotificationResource, status_code=201)
async def create_notification(
    data: NotificationCreateResource,
    db: AsyncSession = Depends(get_db),
) -> NotificationResource:
    """Create a new notification."""
    notification = await notification_service.create_notification(db, data)
    return NotificationResource.model_validate(notification)


@router.put("/{notification_id}", response_model=NotificationResource)
async def update_notification(
    notification_id: int,
    data: NotificationUpdateResource,
    db: AsyncSession = Depends(get_db),
) -> NotificationResource:
    """Update an existing notification."""
    notification = await notification_service.update_notification(db, notification_id, data)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationResource.model_validate(notification)


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a notification."""
    deleted = await notification_service.delete_notification(db, notification_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification not found")


@router.post("/{notification_id}/test", response_model=NotificationTestResult)
async def test_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
) -> NotificationTestResult:
    """Test a notification by sending a test message."""
    success, message = await notification_service.test_notification(db, notification_id)
    if not success and message == "Notification not found.":
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationTestResult(is_valid=success, message=message)
