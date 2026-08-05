from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class EmailSettings(TimestampMixin, Base):
    __tablename__ = "email_settings"
    __table_args__ = (
        CheckConstraint(
            "smtp_security IN ('starttls', 'ssl_tls', 'none')",
            name="ck_email_settings_smtp_security",
        ),
        CheckConstraint(
            "risk_threshold IN ('low', 'medium', 'high', 'critical')",
            name="ck_email_settings_risk_threshold",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")
    enabled: Mapped[bool] = mapped_column(default=False)
    automatic_enabled: Mapped[bool] = mapped_column(default=False)
    risk_threshold: Mapped[str] = mapped_column(String(16), default="high")
    retry_enabled: Mapped[bool] = mapped_column(default=True)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_security: Mapped[str] = mapped_column(String(16), default="starttls")
    smtp_username: Mapped[str | None] = mapped_column(String(320), nullable=True)
    smtp_password_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reply_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15)
    subject_template: Mapped[str] = mapped_column(String(500))
    text_body_template: Mapped[str] = mapped_column(Text)
    html_body_template: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}


class EmailDelivery(TimestampMixin, Base):
    __tablename__ = "email_deliveries"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('automatic', 'manual', 'test', 'manual_retry')",
            name="ck_email_deliveries_trigger_type",
        ),
        CheckConstraint(
            "status IN ('queued', 'sending', 'retry_scheduled', 'sent', 'failed', 'skipped')",
            name="ck_email_deliveries_status",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    trigger_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    dedupe_key: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    source_event_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("system_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    retry_of_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("email_deliveries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recipient_person_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(
        String(320), nullable=True, index=True
    )
    subject: Mapped[str] = mapped_column(String(500), default="")
    text_body: Mapped[str] = mapped_column(Text, default="")
    html_body: Mapped[str] = mapped_column(Text, default="")
    risk_count: Mapped[int] = mapped_column(Integer, default=0)
    match_result_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    skip_reason: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    requested_by_user_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )

    source_event: Mapped["SystemEvent | None"] = relationship()
    retry_of: Mapped["EmailDelivery | None"] = relationship(
        remote_side="EmailDelivery.id"
    )
    attempts: Mapped[list["EmailDeliveryAttempt"]] = relationship(
        back_populates="delivery",
        cascade="all, delete-orphan",
        order_by="EmailDeliveryAttempt.attempt_number",
    )


class EmailDeliveryAttempt(TimestampMixin, Base):
    __tablename__ = "email_delivery_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('sent', 'failed')",
            name="ck_email_delivery_attempts_status",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    email_delivery_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_deliveries.id", ondelete="CASCADE"),
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    delivery: Mapped[EmailDelivery] = relationship(back_populates="attempts")
