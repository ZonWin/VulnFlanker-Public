"""add rule numeric configs

Revision ID: 1b2c3d4e5f60
Revises: c9d1e2f3a4b6
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "1b2c3d4e5f60"
down_revision = "c9d1e2f3a4b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "rule_numeric_configs" not in tables:
        op.create_table(
            "rule_numeric_configs",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("model_version", sa.String(length=32), nullable=False),
            sa.Column("matching_confidences_json", sa.JSON(), nullable=False),
            sa.Column("risk_factor_values_json", sa.JSON(), nullable=False),
            sa.Column("risk_weights_json", sa.JSON(), nullable=False),
            sa.Column("risk_priority_thresholds_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "rule_numeric_configs" in tables:
        op.drop_table("rule_numeric_configs")
