"""add risk snapshots

Revision ID: f6c1d2e3a4b5
Revises: e4b8f1a2c3d4
Create Date: 2026-05-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f6c1d2e3a4b5"
down_revision = "e4b8f1a2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("match_results")}

    if "risk_priority" not in columns:
        op.add_column(
            "match_results",
            sa.Column(
                "risk_priority",
                sa.String(length=32),
                nullable=False,
                server_default="none",
            ),
        )
    if "risk_model_version" not in columns:
        op.add_column(
            "match_results",
            sa.Column(
                "risk_model_version",
                sa.String(length=32),
                nullable=False,
                server_default="risk-v1",
            ),
        )
    if "risk_factors_json" not in columns:
        op.add_column(
            "match_results",
            sa.Column(
                "risk_factors_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
        )
    if "risk_explanation" not in columns:
        op.add_column("match_results", sa.Column("risk_explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("match_results")}

    if "risk_explanation" in columns:
        op.drop_column("match_results", "risk_explanation")
    if "risk_factors_json" in columns:
        op.drop_column("match_results", "risk_factors_json")
    if "risk_model_version" in columns:
        op.drop_column("match_results", "risk_model_version")
    if "risk_priority" in columns:
        op.drop_column("match_results", "risk_priority")
