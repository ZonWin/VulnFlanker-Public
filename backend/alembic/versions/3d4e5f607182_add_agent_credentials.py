"""add agent credentials

Revision ID: 3d4e5f607182
Revises: 2c3d4e5f6071
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "3d4e5f607182"
down_revision = "2c3d4e5f6071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "agent_enrollment_tokens" not in tables:
        op.create_table(
            "agent_enrollment_tokens",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("max_uses", sa.Integer(), nullable=True),
            sa.Column("used_count", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_enrollment_tokens_token_hash", "agent_enrollment_tokens", ["token_hash"], unique=True)
        op.create_index("ix_agent_enrollment_tokens_expires_at", "agent_enrollment_tokens", ["expires_at"])
        op.create_index("ix_agent_enrollment_tokens_created_by", "agent_enrollment_tokens", ["created_by"])
        op.create_index("ix_agent_enrollment_tokens_revoked_at", "agent_enrollment_tokens", ["revoked_at"])

    if "agent_credentials" not in tables:
        op.create_table(
            "agent_credentials",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("agent_id", sa.String(length=128), nullable=False),
            sa.Column("secret_hash", sa.String(length=64), nullable=False),
            sa.Column("secret_version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_credentials_agent_id", "agent_credentials", ["agent_id"])
        op.create_index("ix_agent_credentials_secret_hash", "agent_credentials", ["secret_hash"], unique=True)
        op.create_index("ix_agent_credentials_status", "agent_credentials", ["status"])
        op.create_index("ix_agent_credentials_expires_at", "agent_credentials", ["expires_at"])
        op.create_index("ix_agent_credentials_revoked_at", "agent_credentials", ["revoked_at"])

    if "agent_auth_events" not in tables:
        op.create_table(
            "agent_auth_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("agent_id", sa.String(length=128), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("ip_address", sa.String(length=128), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_auth_events_agent_id", "agent_auth_events", ["agent_id"])
        op.create_index("ix_agent_auth_events_event_type", "agent_auth_events", ["event_type"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "agent_auth_events" in tables:
        op.drop_index("ix_agent_auth_events_event_type", table_name="agent_auth_events")
        op.drop_index("ix_agent_auth_events_agent_id", table_name="agent_auth_events")
        op.drop_table("agent_auth_events")

    if "agent_credentials" in tables:
        op.drop_index("ix_agent_credentials_revoked_at", table_name="agent_credentials")
        op.drop_index("ix_agent_credentials_expires_at", table_name="agent_credentials")
        op.drop_index("ix_agent_credentials_status", table_name="agent_credentials")
        op.drop_index("ix_agent_credentials_secret_hash", table_name="agent_credentials")
        op.drop_index("ix_agent_credentials_agent_id", table_name="agent_credentials")
        op.drop_table("agent_credentials")

    if "agent_enrollment_tokens" in tables:
        op.drop_index("ix_agent_enrollment_tokens_revoked_at", table_name="agent_enrollment_tokens")
        op.drop_index("ix_agent_enrollment_tokens_created_by", table_name="agent_enrollment_tokens")
        op.drop_index("ix_agent_enrollment_tokens_expires_at", table_name="agent_enrollment_tokens")
        op.drop_index("ix_agent_enrollment_tokens_token_hash", table_name="agent_enrollment_tokens")
        op.drop_table("agent_enrollment_tokens")
