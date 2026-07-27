"""add audit logs

Revision ID: c2f4e6a8b901
Revises: b7c9d2e4f601
Create Date: 2026-05-07 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c2f4e6a8b901"
down_revision = "b7c9d2e4f601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("actor_type", sa.String(length=32), nullable=False),
            sa.Column("actor_id", sa.String(length=255), nullable=True),
            sa.Column("action", sa.String(length=128), nullable=False),
            sa.Column("resource_type", sa.String(length=64), nullable=False),
            sa.Column("resource_id", sa.String(length=255), nullable=True),
            sa.Column("outcome", sa.String(length=32), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("details_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
        op.create_index(
            op.f("ix_audit_logs_actor_id"),
            "audit_logs",
            ["actor_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_audit_logs_actor_type"),
            "audit_logs",
            ["actor_type"],
            unique=False,
        )
        op.create_index(
            op.f("ix_audit_logs_outcome"),
            "audit_logs",
            ["outcome"],
            unique=False,
        )
        op.create_index(
            op.f("ix_audit_logs_resource_id"),
            "audit_logs",
            ["resource_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_audit_logs_resource_type"),
            "audit_logs",
            ["resource_type"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "audit_logs" in tables:
        op.drop_index(op.f("ix_audit_logs_resource_type"), table_name="audit_logs")
        op.drop_index(op.f("ix_audit_logs_resource_id"), table_name="audit_logs")
        op.drop_index(op.f("ix_audit_logs_outcome"), table_name="audit_logs")
        op.drop_index(op.f("ix_audit_logs_actor_type"), table_name="audit_logs")
        op.drop_index(op.f("ix_audit_logs_actor_id"), table_name="audit_logs")
        op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
        op.drop_table("audit_logs")
