"""add ai enrichment batch runs

Revision ID: 7b2c3d4e5f60
Revises: 6a1b2c3d4e5f
Create Date: 2026-05-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "7b2c3d4e5f60"
down_revision = "6a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ai_enrichment_batch_runs" not in tables:
        op.create_table(
            "ai_enrichment_batch_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("trigger_type", sa.String(length=32), nullable=False),
            sa.Column("requested_by", sa.String(length=36), nullable=True),
            sa.Column("task_id", sa.String(length=255), nullable=True),
            sa.Column("filters_json", sa.JSON(), nullable=False),
            sa.Column("allow_web_enrichment", sa.Boolean(), nullable=False),
            sa.Column("selected_count", sa.Integer(), nullable=False),
            sa.Column("processed_count", sa.Integer(), nullable=False),
            sa.Column("success_count", sa.Integer(), nullable=False),
            sa.Column("failed_count", sa.Integer(), nullable=False),
            sa.Column("skipped_count", sa.Integer(), nullable=False),
            sa.Column("pending_review_count", sa.Integer(), nullable=False),
            sa.Column("insufficient_count", sa.Integer(), nullable=False),
            sa.Column("recent_error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_ai_enrichment_batch_runs_status",
            "ai_enrichment_batch_runs",
            ["status"],
        )
        op.create_index(
            "ix_ai_enrichment_batch_runs_trigger_type",
            "ai_enrichment_batch_runs",
            ["trigger_type"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "ai_enrichment_batch_runs" in tables:
        op.drop_table("ai_enrichment_batch_runs")
