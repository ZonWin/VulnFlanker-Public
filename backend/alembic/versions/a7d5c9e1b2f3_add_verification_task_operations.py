"""Add verification task retry and cancel fields.

Revision ID: a7d5c9e1b2f3
Revises: f6c1d2e3a4b5
Create Date: 2026-05-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7d5c9e1b2f3"
down_revision = "f6c1d2e3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("verification_tasks")}

    if "previous_task_id" not in columns:
        op.add_column(
            "verification_tasks",
            sa.Column("previous_task_id", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "fk_verification_tasks_previous_task_id",
            "verification_tasks",
            "verification_tasks",
            ["previous_task_id"],
            ["id"],
        )
        op.create_index(
            op.f("ix_verification_tasks_previous_task_id"),
            "verification_tasks",
            ["previous_task_id"],
            unique=False,
        )

    if "cancel_requested_at" not in columns:
        op.add_column(
            "verification_tasks",
            sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("verification_tasks")}

    if "cancel_requested_at" in columns:
        op.drop_column("verification_tasks", "cancel_requested_at")

    if "previous_task_id" in columns:
        op.drop_index(
            op.f("ix_verification_tasks_previous_task_id"),
            table_name="verification_tasks",
        )
        op.drop_constraint(
            "fk_verification_tasks_previous_task_id",
            "verification_tasks",
            type_="foreignkey",
        )
        op.drop_column("verification_tasks", "previous_task_id")
