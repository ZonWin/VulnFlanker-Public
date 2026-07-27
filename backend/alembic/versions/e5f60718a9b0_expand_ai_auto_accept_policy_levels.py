"""expand ai auto accept policy levels

Revision ID: e5f60718a9b0
Revises: d4e5f60718a9
Create Date: 2026-07-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "e5f60718a9b0"
down_revision = "d4e5f60718a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}
    if "ai_auto_accept_policy" in columns:
        op.execute(
            sa.text(
                "UPDATE platform_settings "
                "SET ai_auto_accept_policy = 'moderate' "
                "WHERE ai_auto_accept_policy = 'relaxed'"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}
    if "ai_auto_accept_policy" in columns:
        op.execute(
            sa.text(
                "UPDATE platform_settings "
                "SET ai_auto_accept_policy = 'relaxed' "
                "WHERE ai_auto_accept_policy = 'moderate'"
            )
        )
