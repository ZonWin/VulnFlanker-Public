from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow


class SystemEvent(TimestampMixin, Base):
    __tablename__ = "system_events"
    __table_args__ = (
        CheckConstraint(
            "category IN ('asset', 'intel', 'risk')",
            name="ck_system_events_category",
        ),
        CheckConstraint(
            "level IN ('info', 'success', 'warning', 'error')",
            name="ck_system_events_level",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    event_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info", index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    target_query_json: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    notification: Mapped["AdminNotification | None"] = relationship(
        back_populates="system_event",
        cascade="all, delete-orphan",
        uselist=False,
    )


class AdminNotification(TimestampMixin, Base):
    __tablename__ = "admin_notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    system_event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("system_events.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    system_event: Mapped[SystemEvent] = relationship(back_populates="notification")
