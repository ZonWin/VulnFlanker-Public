"""disable cisa kev monitor by default

Revision ID: d9e8f7a6b5c4
Revises: d8e7f6a5b4c3
Create Date: 2026-08-06 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d9e8f7a6b5c4"
down_revision = "d8e7f6a5b4c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "cisa_kev_monitor_configs" not in tables:
        return

    op.execute(
        sa.text(
            "UPDATE cisa_kev_monitor_configs "
            "SET enabled = false, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = 'default'"
        )
    )


def downgrade() -> None:
    pass
