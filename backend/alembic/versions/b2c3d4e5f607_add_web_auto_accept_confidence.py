"""add web auto accept confidence

Revision ID: b2c3d4e5f607
Revises: a1b2c3d4e5f6
Create Date: 2026-07-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f607"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}
    if "ai_web_auto_accept_confidence" not in columns:
        with op.batch_alter_table("platform_settings") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "ai_web_auto_accept_confidence",
                    sa.Float(),
                    nullable=False,
                    server_default="0.8",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}
    if "ai_web_auto_accept_confidence" in columns:
        with op.batch_alter_table("platform_settings") as batch_op:
            batch_op.drop_column("ai_web_auto_accept_confidence")
