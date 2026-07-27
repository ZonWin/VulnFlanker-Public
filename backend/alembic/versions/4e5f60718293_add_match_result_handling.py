"""add match result handling

Revision ID: 4e5f60718293
Revises: 3d4e5f607182
Create Date: 2026-05-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "4e5f60718293"
down_revision = "3d4e5f607182"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    match_result_columns = {
        column["name"] for column in inspector.get_columns("match_results")
    }

    if "handling_status" not in match_result_columns:
        op.add_column(
            "match_results",
            sa.Column(
                "handling_status",
                sa.String(length=32),
                nullable=False,
                server_default="unprocessed",
            ),
        )
        op.create_index(
            op.f("ix_match_results_handling_status"),
            "match_results",
            ["handling_status"],
            unique=False,
        )
    if "handling_note" not in match_result_columns:
        op.add_column("match_results", sa.Column("handling_note", sa.Text(), nullable=True))
    if "handling_updated_by" not in match_result_columns:
        op.add_column(
            "match_results",
            sa.Column("handling_updated_by", sa.String(length=36), nullable=True),
        )
        op.create_index(
            op.f("ix_match_results_handling_updated_by"),
            "match_results",
            ["handling_updated_by"],
            unique=False,
        )
    if "handling_updated_at" not in match_result_columns:
        op.add_column(
            "match_results",
            sa.Column("handling_updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "handling_closed_at" not in match_result_columns:
        op.add_column(
            "match_results",
            sa.Column("handling_closed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            op.f("ix_match_results_handling_closed_at"),
            "match_results",
            ["handling_closed_at"],
            unique=False,
        )

    tables = set(inspector.get_table_names())
    if "match_result_handling_records" not in tables:
        op.create_table(
            "match_result_handling_records",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("match_result_id", sa.String(length=36), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("from_status", sa.String(length=32), nullable=True),
            sa.Column("to_status", sa.String(length=32), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("actor_id", sa.String(length=36), nullable=True),
            sa.Column("actor_username", sa.String(length=150), nullable=True),
            sa.Column("actor_display_name", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["match_result_id"],
                ["match_results.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_match_result_handling_records_action"),
            "match_result_handling_records",
            ["action"],
            unique=False,
        )
        op.create_index(
            op.f("ix_match_result_handling_records_actor_id"),
            "match_result_handling_records",
            ["actor_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_match_result_handling_records_match_result_id"),
            "match_result_handling_records",
            ["match_result_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_match_result_handling_records_to_status"),
            "match_result_handling_records",
            ["to_status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "match_result_handling_records" in tables:
        op.drop_index(
            op.f("ix_match_result_handling_records_to_status"),
            table_name="match_result_handling_records",
        )
        op.drop_index(
            op.f("ix_match_result_handling_records_match_result_id"),
            table_name="match_result_handling_records",
        )
        op.drop_index(
            op.f("ix_match_result_handling_records_actor_id"),
            table_name="match_result_handling_records",
        )
        op.drop_index(
            op.f("ix_match_result_handling_records_action"),
            table_name="match_result_handling_records",
        )
        op.drop_table("match_result_handling_records")

    match_result_columns = {
        column["name"] for column in inspector.get_columns("match_results")
    }
    if "handling_closed_at" in match_result_columns:
        op.drop_index(op.f("ix_match_results_handling_closed_at"), table_name="match_results")
        op.drop_column("match_results", "handling_closed_at")
    if "handling_updated_at" in match_result_columns:
        op.drop_column("match_results", "handling_updated_at")
    if "handling_updated_by" in match_result_columns:
        op.drop_index(op.f("ix_match_results_handling_updated_by"), table_name="match_results")
        op.drop_column("match_results", "handling_updated_by")
    if "handling_note" in match_result_columns:
        op.drop_column("match_results", "handling_note")
    if "handling_status" in match_result_columns:
        op.drop_index(op.f("ix_match_results_handling_status"), table_name="match_results")
        op.drop_column("match_results", "handling_status")
