"""add ai profile custom prompts

Revision ID: d6f7a8b9c0d1
Revises: a8b9c0d1e2f3
Create Date: 2026-07-24 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d6f7a8b9c0d1"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("ai_profiles")}
    with op.batch_alter_table("ai_profiles") as batch_op:
        if "custom_system_prompt" not in columns:
            batch_op.add_column(sa.Column("custom_system_prompt", sa.Text(), nullable=True))
        if "custom_user_prompt_template" not in columns:
            batch_op.add_column(sa.Column("custom_user_prompt_template", sa.Text(), nullable=True))
        if "custom_output_contract" not in columns:
            batch_op.add_column(sa.Column("custom_output_contract", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("ai_profiles")}
    with op.batch_alter_table("ai_profiles") as batch_op:
        if "custom_output_contract" in columns:
            batch_op.drop_column("custom_output_contract")
        if "custom_user_prompt_template" in columns:
            batch_op.drop_column("custom_user_prompt_template")
        if "custom_system_prompt" in columns:
            batch_op.drop_column("custom_system_prompt")
