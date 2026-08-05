from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


EventCategory = Literal["asset", "intel", "risk"]
EventLevel = Literal["info", "success", "warning", "error"]


class SystemEventOut(BaseModel):
    id: str
    event_key: str
    category: EventCategory
    event_type: str
    level: EventLevel
    title: str
    summary: str
    details: dict[str, object] = Field(default_factory=dict)
    target_type: str | None = None
    target_id: str | None = None
    target_query: dict[str, object] = Field(default_factory=dict)
    occurred_at: datetime
    created_at: datetime


class AdminNotificationOut(BaseModel):
    id: str
    read_at: datetime | None = None
    expires_at: datetime
    created_at: datetime
    event: SystemEventOut


class NotificationListPage(BaseModel):
    items: list[AdminNotificationOut]
    total: int
    offset: int
    limit: int


class SystemEventListPage(BaseModel):
    items: list[SystemEventOut]
    total: int
    offset: int
    limit: int


class UnreadCountOut(BaseModel):
    count: int


class MarkNotificationsReadOut(BaseModel):
    updated_count: int
