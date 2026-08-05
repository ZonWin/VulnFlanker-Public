from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_superuser
from app.db.models import User
from app.schemas.notification import (
    AdminNotificationOut,
    MarkNotificationsReadOut,
    NotificationListPage,
    SystemEventListPage,
    UnreadCountOut,
)
from app.services.notifications import (
    list_notifications,
    list_system_event_history,
    mark_all_notifications_read,
    mark_notification_read,
    unread_notification_count,
)


router = APIRouter()


@router.get("", response_model=NotificationListPage)
async def get_notifications(
    unread_only: bool = Query(default=True),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> NotificationListPage:
    return list_notifications(db, unread_only=unread_only, offset=offset, limit=limit)


@router.get("/unread-count", response_model=UnreadCountOut)
async def get_unread_count(
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> UnreadCountOut:
    return UnreadCountOut(count=unread_notification_count(db))


@router.get("/history", response_model=SystemEventListPage)
async def get_notification_history(
    category: str | None = Query(default=None, pattern="^(asset|intel|risk)$"),
    event_type: str | None = Query(default=None, max_length=64),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> SystemEventListPage:
    return list_system_event_history(
        db,
        category=category,
        event_type=event_type,
        offset=offset,
        limit=limit,
    )


@router.post("/{notification_id}/read", response_model=AdminNotificationOut)
async def read_notification(
    notification_id: str,
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AdminNotificationOut:
    result = mark_notification_read(db, notification_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


@router.post("/read-all", response_model=MarkNotificationsReadOut)
async def read_all_notifications(
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> MarkNotificationsReadOut:
    return MarkNotificationsReadOut(updated_count=mark_all_notifications_read(db))
