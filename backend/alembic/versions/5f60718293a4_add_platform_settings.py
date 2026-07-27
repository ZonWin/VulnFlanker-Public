"""add platform settings

Revision ID: 5f60718293a4
Revises: 4e5f60718293
Create Date: 2026-05-23 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "5f60718293a4"
down_revision = "4e5f60718293"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "platform_settings" not in tables:
        op.create_table(
            "platform_settings",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("platform_name", sa.String(length=80), nullable=False),
            sa.Column("platform_subtitle", sa.String(length=120), nullable=False),
            sa.Column("logo_data_url", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "platform_settings" in tables:
        op.drop_table("platform_settings")
