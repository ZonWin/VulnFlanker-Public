"""seed default ai profiles

Revision ID: 9c4d5e6f7081
Revises: 8c3d4e5f6071
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "9c4d5e6f7081"
down_revision = "8c3d4e5f6071"
branch_labels = None
depends_on = None


DEFAULT_AI_PROFILES = [
    {
        "profile_key": "basic_extraction_profile",
        "display_name": "由大模型对已获取的漏洞信息进行进一步结构化提取，对没有标准格式的漏洞信息源效果较佳。",
        "provider": "fake",
        "base_url": None,
        "api_key_ciphertext": None,
        "model": "fake-json-model",
        "enabled": True,
        "supports_web_search": False,
        "allow_external_network": False,
        "json_mode": True,
        "timeout_seconds": 30,
        "max_tokens": None,
        "temperature": 0.0,
        "daily_call_limit": None,
        "daily_token_limit": None,
    },
    {
        "profile_key": "web_enrichment_profile",
        "display_name": "由大模型结合联网搜索补充漏洞信息，适合本地情报缺少影响版本、修复版本或厂商公告证据时使用。",
        "provider": "fake",
        "base_url": None,
        "api_key_ciphertext": None,
        "model": "fake-web-model",
        "enabled": True,
        "supports_web_search": True,
        "allow_external_network": False,
        "json_mode": True,
        "timeout_seconds": 30,
        "max_tokens": None,
        "temperature": 0.0,
        "daily_call_limit": None,
        "daily_token_limit": None,
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    ai_profiles = _ai_profiles_table()
    keys = [profile["profile_key"] for profile in DEFAULT_AI_PROFILES]
    existing_keys = set(
        bind.execute(
            sa.select(ai_profiles.c.profile_key).where(
                ai_profiles.c.profile_key.in_(keys)
            )
        ).scalars()
    )
    now = datetime.now(timezone.utc)
    records = [
        {
            "id": str(uuid4()),
            **profile,
            "created_at": now,
            "updated_at": now,
        }
        for profile in DEFAULT_AI_PROFILES
        if profile["profile_key"] not in existing_keys
    ]
    if records:
        bind.execute(ai_profiles.insert(), records)


def downgrade() -> None:
    pass


def _ai_profiles_table() -> sa.TableClause:
    return sa.table(
        "ai_profiles",
        sa.column("id", sa.String),
        sa.column("profile_key", sa.String),
        sa.column("display_name", sa.String),
        sa.column("provider", sa.String),
        sa.column("base_url", sa.Text),
        sa.column("api_key_ciphertext", sa.Text),
        sa.column("model", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("supports_web_search", sa.Boolean),
        sa.column("allow_external_network", sa.Boolean),
        sa.column("json_mode", sa.Boolean),
        sa.column("timeout_seconds", sa.Integer),
        sa.column("max_tokens", sa.Integer),
        sa.column("temperature", sa.Float),
        sa.column("daily_call_limit", sa.Integer),
        sa.column("daily_token_limit", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
