"""add ai automation settings

Revision ID: 8c3d4e5f6071
Revises: 7b2c3d4e5f60
Create Date: 2026-05-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "8c3d4e5f6071"
down_revision = "7b2c3d4e5f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}

    additions = [
        ("ai_enabled", sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.true())),
        (
            "ai_auto_enrich_enabled",
            sa.Column("ai_auto_enrich_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
        (
            "ai_auto_accept_enabled",
            sa.Column("ai_auto_accept_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
        (
            "ai_auto_accept_confidence",
            sa.Column("ai_auto_accept_confidence", sa.Float(), nullable=False, server_default="0.85"),
        ),
        (
            "ai_layer2_daily_limit",
            sa.Column("ai_layer2_daily_limit", sa.Integer(), nullable=False, server_default="50"),
        ),
        (
            "ai_batch_max_size",
            sa.Column("ai_batch_max_size", sa.Integer(), nullable=False, server_default="100"),
        ),
        (
            "ai_allow_web_enrichment_default",
            sa.Column(
                "ai_allow_web_enrichment_default",
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
    columns = {column["name"] for column in inspector.get_columns("platform_settings")}
    removable = [
        "ai_allow_web_enrichment_default",
        "ai_batch_max_size",
        "ai_layer2_daily_limit",
        "ai_auto_accept_confidence",
        "ai_auto_accept_enabled",
        "ai_auto_enrich_enabled",
        "ai_enabled",
    ]
    with op.batch_alter_table("platform_settings") as batch_op:
        for name in removable:
            if name in columns:
                batch_op.drop_column(name)
