from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.db.models import AdminNotification, SystemEvent
from app.schemas.notification import (
    AdminNotificationOut,
    NotificationListPage,
    SystemEventListPage,
    SystemEventOut,
)


NOTIFICATION_RETENTION_DAYS = 30
ALLOWED_TARGET_TYPES = {
    "asset",
    "asset_list",
    "intel_run",
    "risk",
    "risk_evaluation",
}


def create_system_event(
    db: Session,
    *,
    event_key: str,
    category: str,
    event_type: str,
    level: str,
    title: str,
    summary: str,
    details: dict[str, Any] | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    target_query: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
    notify_admin: bool = True,
) -> SystemEvent:
    existing = db.scalar(select(SystemEvent).where(SystemEvent.event_key == event_key))
    if existing is not None:
        return existing
    if target_type is not None and target_type not in ALLOWED_TARGET_TYPES:
        raise ValueError(f"Unsupported notification target type: {target_type}")

    event_time = occurred_at or utcnow()
    event = SystemEvent(
        event_key=event_key,
        category=category,
        event_type=event_type,
        level=level,
        title=title.strip(),
        summary=summary.strip(),
        details_json=details or {},
        target_type=target_type,
        target_id=target_id,
        target_query_json=target_query or {},
        occurred_at=event_time,
    )
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
            if notify_admin:
                notification = AdminNotification(
                    system_event_id=event.id,
                    expires_at=event_time + timedelta(days=NOTIFICATION_RETENTION_DAYS),
                )
                db.add(notification)
                db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SystemEvent).where(SystemEvent.event_key == event_key)
        )
        if existing is None:
            raise
        return existing
    return event


def list_notifications(
    db: Session,
    *,
    unread_only: bool = True,
    offset: int = 0,
    limit: int = 100,
) -> NotificationListPage:
    now = utcnow()
    conditions = [AdminNotification.expires_at > now]
    if unread_only:
        conditions.append(AdminNotification.read_at.is_(None))
    total = int(
        db.scalar(select(func.count(AdminNotification.id)).where(*conditions)) or 0
    )
    statement = (
        select(AdminNotification)
        .options(selectinload(AdminNotification.system_event))
        .where(*conditions)
        .order_by(desc(AdminNotification.created_at))
        .offset(offset)
        .limit(limit)
    )
    items = [_to_notification_out(item) for item in db.scalars(statement).all()]
    return NotificationListPage(items=items, total=total, offset=offset, limit=limit)


def unread_notification_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(AdminNotification.id)).where(
                AdminNotification.read_at.is_(None),
                AdminNotification.expires_at > utcnow(),
            )
        )
        or 0
    )


def mark_notification_read(
    db: Session,
    notification_id: str,
) -> AdminNotificationOut | None:
    notification = db.scalar(
        select(AdminNotification)
        .options(selectinload(AdminNotification.system_event))
        .where(
            AdminNotification.id == notification_id,
            AdminNotification.expires_at > utcnow(),
        )
    )
    if notification is None:
        return None
    if notification.read_at is None:
        notification.read_at = utcnow()
        db.add(notification)
        db.commit()
        db.refresh(notification)
    return _to_notification_out(notification)


def mark_all_notifications_read(db: Session) -> int:
    now = utcnow()
    result = db.execute(
        update(AdminNotification)
        .where(
            AdminNotification.read_at.is_(None),
            AdminNotification.expires_at > now,
        )
        .values(read_at=now, updated_at=now)
    )
    db.commit()
    return int(result.rowcount or 0)


def list_system_event_history(
    db: Session,
    *,
    category: str | None = None,
    event_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> SystemEventListPage:
    conditions = []
    if category:
        conditions.append(SystemEvent.category == category)
    if event_type:
        conditions.append(SystemEvent.event_type == event_type)
    total = int(db.scalar(select(func.count(SystemEvent.id)).where(*conditions)) or 0)
    statement = (
        select(SystemEvent)
        .where(*conditions)
        .order_by(desc(SystemEvent.occurred_at), desc(SystemEvent.created_at))
        .offset(offset)
        .limit(limit)
    )
    return SystemEventListPage(
        items=[_to_event_out(item) for item in db.scalars(statement).all()],
        total=total,
        offset=offset,
        limit=limit,
    )


def cleanup_expired_notifications(db: Session) -> int:
    result = db.execute(
        delete(AdminNotification).where(AdminNotification.expires_at <= utcnow())
    )
    db.commit()
    return int(result.rowcount or 0)


def _to_notification_out(notification: AdminNotification) -> AdminNotificationOut:
    return AdminNotificationOut(
        id=notification.id,
        read_at=notification.read_at,
        expires_at=notification.expires_at,
        created_at=notification.created_at,
        event=_to_event_out(notification.system_event),
    )


def _to_event_out(event: SystemEvent) -> SystemEventOut:
    return SystemEventOut(
        id=event.id,
        event_key=event.event_key,
        category=event.category,
        event_type=event.event_type,
        level=event.level,
        title=event.title,
        summary=event.summary,
        details=event.details_json or {},
        target_type=event.target_type,
        target_id=event.target_id,
        target_query=event.target_query_json or {},
        occurred_at=event.occurred_at,
        created_at=event.created_at,
    )
