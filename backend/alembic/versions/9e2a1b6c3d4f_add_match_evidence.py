"""add match evidence

Revision ID: 9e2a1b6c3d4f
Revises: 4f7d3c2b1a90
Create Date: 2026-05-06 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "9e2a1b6c3d4f"
down_revision = "4f7d3c2b1a90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    match_result_columns = {
        column["name"] for column in inspector.get_columns("match_results")
    }
    if "last_evaluated_at" not in match_result_columns:
        op.add_column(
            "match_results",
            sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        )

    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("match_results")
    }
    if "uq_match_results_vulnerability_asset" not in unique_constraints:
        op.create_unique_constraint(
            "uq_match_results_vulnerability_asset",
            "match_results",
            ["vulnerability_id", "asset_id"],
        )

    tables = set(inspector.get_table_names())
    if "match_evidence" not in tables:
        op.create_table(
            "match_evidence",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("match_result_id", sa.String(length=36), nullable=False),
            sa.Column("evidence_type", sa.String(length=64), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("raw_ref", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("details_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["match_result_id"], ["match_results.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_match_evidence_evidence_type"),
            "match_evidence",
            ["evidence_type"],
            unique=False,
        )
        op.create_index(
            op.f("ix_match_evidence_match_result_id"),
            "match_evidence",
            ["match_result_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "match_evidence" in tables:
        op.drop_index(op.f("ix_match_evidence_match_result_id"), table_name="match_evidence")
        op.drop_index(op.f("ix_match_evidence_evidence_type"), table_name="match_evidence")
        op.drop_table("match_evidence")

    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("match_results")
    }
    if "uq_match_results_vulnerability_asset" in unique_constraints:
        op.drop_constraint(
            "uq_match_results_vulnerability_asset",
            "match_results",
            type_="unique",
        )

    match_result_columns = {
        column["name"] for column in inspector.get_columns("match_results")
    }
    if "last_evaluated_at" in match_result_columns:
        op.drop_column("match_results", "last_evaluated_at")
