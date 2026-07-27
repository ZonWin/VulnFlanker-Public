"""add watchvuln monitor config

Revision ID: 0f1a2b3c4d5e
Revises: f6c1d2e3a4b5
Create Date: 2026-05-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0f1a2b3c4d5e"
down_revision = "f6c1d2e3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "watchvuln_monitor_configs" not in tables:
        op.create_table(
            "watchvuln_monitor_configs",
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
    tables = set(inspector.get_table_names())

    if "watchvuln_monitor_configs" in tables:
        op.drop_table("watchvuln_monitor_configs")
