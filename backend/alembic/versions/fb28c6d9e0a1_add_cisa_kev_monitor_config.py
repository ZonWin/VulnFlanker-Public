"""add cisa kev monitor config

Revision ID: fb28c6d9e0a1
Revises: b4c6d8e0f1a2
Create Date: 2026-07-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "fb28c6d9e0a1"
down_revision = "b4c6d8e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cisa_kev_monitor_configs" in inspector.get_table_names():
        return
    op.create_table(
        "cisa_kev_monitor_configs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cisa_kev_monitor_configs" in inspector.get_table_names():
        op.drop_table("cisa_kev_monitor_configs")
