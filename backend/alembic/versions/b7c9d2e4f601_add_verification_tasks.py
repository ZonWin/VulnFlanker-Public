"""add verification tasks

Revision ID: b7c9d2e4f601
Revises: 9e2a1b6c3d4f
Create Date: 2026-05-06 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "b7c9d2e4f601"
down_revision = "9e2a1b6c3d4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "verification_tasks" not in tables:
        op.create_table(
            "verification_tasks",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("asset_id", sa.String(length=36), nullable=False),
            sa.Column("match_result_id", sa.String(length=36), nullable=False),
            sa.Column("task_type", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("parameters", sa.JSON(), nullable=False),
            sa.Column("requested_by", sa.String(length=255), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_code", sa.String(length=128), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
            sa.ForeignKeyConstraint(["match_result_id"], ["match_results.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_verification_tasks_asset_id"),
            "verification_tasks",
            ["asset_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_verification_tasks_match_result_id"),
            "verification_tasks",
            ["match_result_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_verification_tasks_status"),
            "verification_tasks",
            ["status"],
            unique=False,
        )
        op.create_index(
            op.f("ix_verification_tasks_task_type"),
            "verification_tasks",
            ["task_type"],
            unique=False,
        )

    tables = set(inspector.get_table_names())
    if "verification_evidence" not in tables:
        op.create_table(
            "verification_evidence",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("verification_task_id", sa.String(length=36), nullable=False),
            sa.Column("match_result_id", sa.String(length=36), nullable=False),
            sa.Column("evidence_type", sa.String(length=64), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("raw_ref", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("details_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["match_result_id"], ["match_results.id"]),
            sa.ForeignKeyConstraint(["verification_task_id"], ["verification_tasks.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_verification_evidence_evidence_type"),
            "verification_evidence",
            ["evidence_type"],
            unique=False,
        )
        op.create_index(
            op.f("ix_verification_evidence_match_result_id"),
            "verification_evidence",
            ["match_result_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_verification_evidence_verification_task_id"),
            "verification_evidence",
            ["verification_task_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "verification_evidence" in tables:
        op.drop_index(
            op.f("ix_verification_evidence_verification_task_id"),
            table_name="verification_evidence",
        )
        op.drop_index(
            op.f("ix_verification_evidence_match_result_id"),
            table_name="verification_evidence",
        )
        op.drop_index(
            op.f("ix_verification_evidence_evidence_type"),
            table_name="verification_evidence",
        )
        op.drop_table("verification_evidence")

    tables = set(inspector.get_table_names())
    if "verification_tasks" in tables:
        op.drop_index(op.f("ix_verification_tasks_task_type"), table_name="verification_tasks")
        op.drop_index(op.f("ix_verification_tasks_status"), table_name="verification_tasks")
        op.drop_index(
            op.f("ix_verification_tasks_match_result_id"),
            table_name="verification_tasks",
        )
        op.drop_index(op.f("ix_verification_tasks_asset_id"), table_name="verification_tasks")
        op.drop_table("verification_tasks")
