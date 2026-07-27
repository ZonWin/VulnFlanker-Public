"""add ai profile model vendor

Revision ID: a1b2c3d4e5f6
Revises: 9c4d5e6f7081
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9c4d5e6f7081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_profiles",
        sa.Column(
            "model_vendor",
            sa.String(length=64),
            nullable=False,
            server_default="openai",
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_profiles", "model_vendor")
