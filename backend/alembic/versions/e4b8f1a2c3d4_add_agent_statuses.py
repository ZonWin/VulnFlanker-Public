"""add agent statuses

Revision ID: e4b8f1a2c3d4
Revises: d3a7e9f0c1b2
Create Date: 2026-05-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "e4b8f1a2c3d4"
down_revision = "d3a7e9f0c1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "agent_statuses" not in tables:
        op.create_table(
            "agent_statuses",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("agent_id", sa.String(length=128), nullable=False),
            sa.Column("hostname", sa.String(length=255), nullable=True),
            sa.Column("platform", sa.String(length=64), nullable=True),
            sa.Column("version", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_snapshot_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_task_poll_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("agent_id"),
        )
        op.create_index(op.f("ix_agent_statuses_agent_id"), "agent_statuses", ["agent_id"], unique=False)
        op.create_index(op.f("ix_agent_statuses_status"), "agent_statuses", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "agent_statuses" in tables:
        op.drop_index(op.f("ix_agent_statuses_status"), table_name="agent_statuses")
        op.drop_index(op.f("ix_agent_statuses_agent_id"), table_name="agent_statuses")
        op.drop_table("agent_statuses")
