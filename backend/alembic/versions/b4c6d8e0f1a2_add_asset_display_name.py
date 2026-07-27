"""add asset display name

Revision ID: b4c6d8e0f1a2
Revises: fa17b2c3d4e5
Create Date: 2026-07-17 11:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b4c6d8e0f1a2"
down_revision = "fa17b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("display_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "display_name")
