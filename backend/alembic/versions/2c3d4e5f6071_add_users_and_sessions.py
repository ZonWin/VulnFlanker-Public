"""add users and sessions

Revision ID: 2c3d4e5f6071
Revises: 1b2c3d4e5f60
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "2c3d4e5f6071"
down_revision = "1b2c3d4e5f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("username", sa.String(length=150), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column("is_superuser", sa.Boolean(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_username", "users", ["username"], unique=True)
        op.create_index("ix_users_is_superuser", "users", ["is_superuser"])
        op.create_index("ix_users_is_active", "users", ["is_active"])

    if "user_sessions" not in tables:
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
        op.create_index(
            "ix_user_sessions_token_hash",
            "user_sessions",
            ["token_hash"],
            unique=True,
        )
        op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
        op.create_index("ix_user_sessions_revoked_at", "user_sessions", ["revoked_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "user_sessions" in tables:
        op.drop_index("ix_user_sessions_revoked_at", table_name="user_sessions")
        op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
        op.drop_index("ix_user_sessions_token_hash", table_name="user_sessions")
        op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
        op.drop_table("user_sessions")

    if "users" in tables:
        op.drop_index("ix_users_is_active", table_name="users")
        op.drop_index("ix_users_is_superuser", table_name="users")
        op.drop_index("ix_users_username", table_name="users")
        op.drop_table("users")
