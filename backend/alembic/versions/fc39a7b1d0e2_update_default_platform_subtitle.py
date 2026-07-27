"""update default platform subtitle

Revision ID: fc39a7b1d0e2
Revises: fb28c6d9e0a1
Create Date: 2026-07-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "fc39a7b1d0e2"
down_revision = "fb28c6d9e0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE platform_settings
            SET platform_name = :default_name,
                platform_subtitle = :new_subtitle
            WHERE id = :settings_id
              AND platform_name IN (:default_name, :wrong_name)
              AND platform_subtitle = :old_subtitle
            """
        ).bindparams(
            settings_id="default",
            default_name="VulnFlanker",
            wrong_name="漏洞监测平台",
            old_subtitle="漏洞管理平台",
            new_subtitle="漏洞监测平台",
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE platform_settings
            SET platform_subtitle = :old_subtitle
            WHERE id = :settings_id
              AND platform_name = :default_name
              AND platform_subtitle = :new_subtitle
            """
        ).bindparams(
            settings_id="default",
            default_name="VulnFlanker",
            old_subtitle="漏洞管理平台",
            new_subtitle="漏洞监测平台",
        )
    )
