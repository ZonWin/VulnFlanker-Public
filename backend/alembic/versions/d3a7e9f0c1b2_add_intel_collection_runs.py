"""add intel collection runs

Revision ID: d3a7e9f0c1b2
Revises: c2f4e6a8b901
Create Date: 2026-05-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d3a7e9f0c1b2"
down_revision = "c2f4e6a8b901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "intel_collection_runs" not in tables:
        op.create_table(
            "intel_collection_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("source_name", sa.String(length=64), nullable=False),
            sa.Column("trigger_type", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("fetched_count", sa.Integer(), nullable=False),
            sa.Column("stored_count", sa.Integer(), nullable=False),
            sa.Column("processed_count", sa.Integer(), nullable=False),
            sa.Column("skipped_count", sa.Integer(), nullable=False),
            sa.Column("failed_count", sa.Integer(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("task_id", sa.String(length=255), nullable=True),
            sa.Column("parameters_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_intel_collection_runs_source_name"),
            "intel_collection_runs",
            ["source_name"],
            unique=False,
        )
        op.create_index(
            op.f("ix_intel_collection_runs_status"),
            "intel_collection_runs",
            ["status"],
            unique=False,
        )
        op.create_index(
            op.f("ix_intel_collection_runs_task_id"),
            "intel_collection_runs",
            ["task_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_intel_collection_runs_trigger_type"),
            "intel_collection_runs",
            ["trigger_type"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "intel_collection_runs" in tables:
        op.drop_index(op.f("ix_intel_collection_runs_trigger_type"), table_name="intel_collection_runs")
        op.drop_index(op.f("ix_intel_collection_runs_task_id"), table_name="intel_collection_runs")
        op.drop_index(op.f("ix_intel_collection_runs_status"), table_name="intel_collection_runs")
        op.drop_index(op.f("ix_intel_collection_runs_source_name"), table_name="intel_collection_runs")
        op.drop_table("intel_collection_runs")
