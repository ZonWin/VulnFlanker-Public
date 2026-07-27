"""add auto matching settings

Revision ID: a8b9c0d1e2f3
Revises: f0e1d2c3b4a5
Create Date: 2026-07-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "a8b9c0d1e2f3"
down_revision = "f0e1d2c3b4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "platform_settings" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}
    additions = [
        (
            "auto_match_on_new_asset",
            sa.Column(
                "auto_match_on_new_asset",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        ),
        (
            "auto_match_on_new_vulnerability",
            sa.Column(
                "auto_match_on_new_vulnerability",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        ),
    ]
    with op.batch_alter_table("platform_settings") as batch_op:
        for name, column in additions:
            if name not in columns:
                batch_op.add_column(column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "platform_settings" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}
    with op.batch_alter_table("platform_settings") as batch_op:
        for name in ("auto_match_on_new_vulnerability", "auto_match_on_new_asset"):
            if name in columns:
                batch_op.drop_column(name)
