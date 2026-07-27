"""add agent enrollment token preview

Revision ID: fd4a8b9c0d1e
Revises: 6b2f4c8e1a73
Create Date: 2026-07-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "fd4a8b9c0d1e"
down_revision = "6b2f4c8e1a73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "agent_enrollment_tokens" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("agent_enrollment_tokens")}
    if "token_preview" not in columns:
        op.add_column(
            "agent_enrollment_tokens",
            sa.Column("token_preview", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "agent_enrollment_tokens" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("agent_enrollment_tokens")}
    if "token_preview" in columns:
        op.drop_column("agent_enrollment_tokens", "token_preview")
