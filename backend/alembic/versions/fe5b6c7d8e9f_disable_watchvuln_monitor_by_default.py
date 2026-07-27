"""disable watchvuln monitor by default

Revision ID: fe5b6c7d8e9f
Revises: fd4a8b9c0d1e
Create Date: 2026-07-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "fe5b6c7d8e9f"
down_revision = "fd4a8b9c0d1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "watchvuln_monitor_configs" not in tables:
        return

    op.execute(
        sa.text(
            "UPDATE watchvuln_monitor_configs "
            "SET enabled = false, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = 'default'"
        )
    )


def downgrade() -> None:
    pass
