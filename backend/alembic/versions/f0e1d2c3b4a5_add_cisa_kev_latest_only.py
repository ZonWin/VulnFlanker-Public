"""add cisa kev latest-only monitor option

Revision ID: f0e1d2c3b4a5
Revises: fe5b6c7d8e9f
Create Date: 2026-07-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f0e1d2c3b4a5"
down_revision = "fe5b6c7d8e9f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cisa_kev_monitor_configs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("cisa_kev_monitor_configs")}
    if "latest_only" in columns:
        return
    op.add_column(
        "cisa_kev_monitor_configs",
        sa.Column("latest_only", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("cisa_kev_monitor_configs", "latest_only", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cisa_kev_monitor_configs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("cisa_kev_monitor_configs")}
    if "latest_only" not in columns:
        return
    op.drop_column("cisa_kev_monitor_configs", "latest_only")
