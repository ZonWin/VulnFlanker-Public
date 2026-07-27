"""add ai auto accept policy

Revision ID: c3d4e5f60718
Revises: b2c3d4e5f607
Create Date: 2026-07-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c3d4e5f60718"
down_revision = "b2c3d4e5f607"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}
    if "ai_auto_accept_policy" not in columns:
        with op.batch_alter_table("platform_settings") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "ai_auto_accept_policy",
                    sa.String(length=32),
                    nullable=False,
                    server_default="relaxed",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}
    if "ai_auto_accept_policy" in columns:
        with op.batch_alter_table("platform_settings") as batch_op:
            batch_op.drop_column("ai_auto_accept_policy")
