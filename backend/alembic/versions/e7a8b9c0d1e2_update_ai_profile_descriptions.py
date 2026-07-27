"""update default ai profile descriptions

Revision ID: e7a8b9c0d1e2
Revises: d6f7a8b9c0d1
Create Date: 2026-07-24 17:50:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "e7a8b9c0d1e2"
down_revision = "d6f7a8b9c0d1"
branch_labels = None
depends_on = None


BASIC_PROFILE_KEY = "basic_extraction_profile"
WEB_PROFILE_KEY = "web_enrichment_profile"

BASIC_DESCRIPTION = (
    "由大模型对已获取的漏洞信息进行进一步结构化提取，"
    "对没有标准格式的漏洞信息源效果较佳。"
)
WEB_DESCRIPTION = (
    "由大模型结合联网搜索补充漏洞信息，"
    "适合本地情报缺少影响版本、修复版本或厂商公告证据时使用。"
)

OLD_BASIC_DESCRIPTIONS = (
    "基础漏洞情报抽取",
    "源信息快速提取",
)
OLD_WEB_DESCRIPTIONS = (
    "联网漏洞情报补全",
    "联网搜索补充",
    "联网搜索",
)


def upgrade() -> None:
    ai_profiles = _ai_profiles_table()
    bind = op.get_bind()
    bind.execute(
        ai_profiles.update()
        .where(ai_profiles.c.profile_key == BASIC_PROFILE_KEY)
        .where(ai_profiles.c.display_name.in_(OLD_BASIC_DESCRIPTIONS))
        .values(display_name=BASIC_DESCRIPTION)
    )
    bind.execute(
        ai_profiles.update()
        .where(ai_profiles.c.profile_key == WEB_PROFILE_KEY)
        .where(ai_profiles.c.display_name.in_(OLD_WEB_DESCRIPTIONS))
        .values(display_name=WEB_DESCRIPTION)
    )


def downgrade() -> None:
    ai_profiles = _ai_profiles_table()
    bind = op.get_bind()
    bind.execute(
        ai_profiles.update()
        .where(ai_profiles.c.profile_key == BASIC_PROFILE_KEY)
        .where(ai_profiles.c.display_name == BASIC_DESCRIPTION)
        .values(display_name="基础漏洞情报抽取")
    )
    bind.execute(
        ai_profiles.update()
        .where(ai_profiles.c.profile_key == WEB_PROFILE_KEY)
        .where(ai_profiles.c.display_name == WEB_DESCRIPTION)
        .values(display_name="联网漏洞情报补全")
    )


def _ai_profiles_table() -> sa.Table:
    return sa.table(
        "ai_profiles",
        sa.column("profile_key", sa.String),
        sa.column("display_name", sa.String),
    )
