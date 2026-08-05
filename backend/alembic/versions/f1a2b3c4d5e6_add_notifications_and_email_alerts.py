"""add notifications and email alerts

Revision ID: f1a2b3c4d5e6
Revises: e7a8b9c0d1e2
Create Date: 2026-08-05 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f1a2b3c4d5e6"
down_revision = "e7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("target_query_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('asset', 'intel', 'risk')",
            name="ck_system_events_category",
        ),
        sa.CheckConstraint(
            "level IN ('info', 'success', 'warning', 'error')",
            name="ck_system_events_level",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key"),
    )
    op.create_index("ix_system_events_event_key", "system_events", ["event_key"])
    op.create_index("ix_system_events_category", "system_events", ["category"])
    op.create_index("ix_system_events_event_type", "system_events", ["event_type"])
    op.create_index("ix_system_events_level", "system_events", ["level"])
    op.create_index("ix_system_events_target_id", "system_events", ["target_id"])
    op.create_index("ix_system_events_occurred_at", "system_events", ["occurred_at"])

    op.create_table(
        "admin_notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_event_id", sa.String(length=36), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_event_id"], ["system_events.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system_event_id"),
    )
    op.create_index(
        "ix_admin_notifications_system_event_id",
        "admin_notifications",
        ["system_event_id"],
    )
    op.create_index("ix_admin_notifications_read_at", "admin_notifications", ["read_at"])
    op.create_index(
        "ix_admin_notifications_expires_at", "admin_notifications", ["expires_at"]
    )

    op.create_table(
        "email_settings",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("automatic_enabled", sa.Boolean(), nullable=False),
        sa.Column("risk_threshold", sa.String(length=16), nullable=False),
        sa.Column("retry_enabled", sa.Boolean(), nullable=False),
        sa.Column("smtp_host", sa.String(length=255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("smtp_security", sa.String(length=16), nullable=False),
        sa.Column("smtp_username", sa.String(length=320), nullable=True),
        sa.Column("smtp_password_ciphertext", sa.Text(), nullable=True),
        sa.Column("sender_name", sa.String(length=255), nullable=True),
        sa.Column("sender_email", sa.String(length=320), nullable=True),
        sa.Column("reply_to", sa.String(length=320), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("subject_template", sa.String(length=500), nullable=False),
        sa.Column("text_body_template", sa.Text(), nullable=False),
        sa.Column("html_body_template", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "smtp_security IN ('starttls', 'ssl_tls', 'none')",
            name="ck_email_settings_smtp_security",
        ),
        sa.CheckConstraint(
            "risk_threshold IN ('low', 'medium', 'high', 'critical')",
            name="ck_email_settings_risk_threshold",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("source_event_id", sa.String(length=36), nullable=True),
        sa.Column("retry_of_id", sa.String(length=36), nullable=True),
        sa.Column("recipient_person_id", sa.String(length=36), nullable=True),
        sa.Column("recipient_name", sa.String(length=255), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("risk_count", sa.Integer(), nullable=False),
        sa.Column("match_result_ids_json", sa.JSON(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("skip_reason", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "trigger_type IN ('automatic', 'manual', 'test', 'manual_retry')",
            name="ck_email_deliveries_trigger_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'sending', 'retry_scheduled', 'sent', 'failed', 'skipped')",
            name="ck_email_deliveries_status",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_id"], ["email_deliveries.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"], ["system_events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    for name in (
        "trigger_type",
        "status",
        "dedupe_key",
        "source_event_id",
        "retry_of_id",
        "recipient_person_id",
        "recipient_email",
        "skip_reason",
        "next_attempt_at",
        "sent_at",
        "requested_by_user_id",
    ):
        op.create_index(f"ix_email_deliveries_{name}", "email_deliveries", [name])

    op.create_table(
        "email_delivery_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email_delivery_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('sent', 'failed')",
            name="ck_email_delivery_attempts_status",
        ),
        sa.ForeignKeyConstraint(
            ["email_delivery_id"], ["email_deliveries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_delivery_attempts_email_delivery_id",
        "email_delivery_attempts",
        ["email_delivery_id"],
    )
    op.create_index(
        "ix_email_delivery_attempts_status",
        "email_delivery_attempts",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_delivery_attempts_status", table_name="email_delivery_attempts"
    )
    op.drop_index(
        "ix_email_delivery_attempts_email_delivery_id",
        table_name="email_delivery_attempts",
    )
    op.drop_table("email_delivery_attempts")
    for name in reversed(
        (
            "trigger_type",
            "status",
            "dedupe_key",
            "source_event_id",
            "retry_of_id",
            "recipient_person_id",
            "recipient_email",
            "skip_reason",
            "next_attempt_at",
            "sent_at",
            "requested_by_user_id",
        )
    ):
        op.drop_index(f"ix_email_deliveries_{name}", table_name="email_deliveries")
    op.drop_table("email_deliveries")
    op.drop_table("email_settings")
    op.drop_index("ix_admin_notifications_expires_at", table_name="admin_notifications")
    op.drop_index("ix_admin_notifications_read_at", table_name="admin_notifications")
    op.drop_index(
        "ix_admin_notifications_system_event_id", table_name="admin_notifications"
    )
    op.drop_table("admin_notifications")
    op.drop_index("ix_system_events_occurred_at", table_name="system_events")
    op.drop_index("ix_system_events_target_id", table_name="system_events")
    op.drop_index("ix_system_events_level", table_name="system_events")
    op.drop_index("ix_system_events_event_type", table_name="system_events")
    op.drop_index("ix_system_events_category", table_name="system_events")
    op.drop_index("ix_system_events_event_key", table_name="system_events")
    op.drop_table("system_events")
