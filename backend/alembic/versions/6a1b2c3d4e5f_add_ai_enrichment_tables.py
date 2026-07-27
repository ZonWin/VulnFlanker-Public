"""add ai enrichment tables

Revision ID: 6a1b2c3d4e5f
Revises: c9d1e2f3a4b6, 5f60718293a4
Create Date: 2026-05-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "6a1b2c3d4e5f"
down_revision = ("c9d1e2f3a4b6", "5f60718293a4")
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ai_profiles" not in tables:
        op.create_table(
            "ai_profiles",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("profile_key", sa.String(length=64), nullable=False),
            sa.Column("display_name", sa.String(length=128), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("base_url", sa.Text(), nullable=True),
            sa.Column("api_key_ciphertext", sa.Text(), nullable=True),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("supports_web_search", sa.Boolean(), nullable=False),
            sa.Column("allow_external_network", sa.Boolean(), nullable=False),
            sa.Column("json_mode", sa.Boolean(), nullable=False),
            sa.Column("timeout_seconds", sa.Integer(), nullable=False),
            sa.Column("max_tokens", sa.Integer(), nullable=True),
            sa.Column("temperature", sa.Float(), nullable=False),
            sa.Column("daily_call_limit", sa.Integer(), nullable=True),
            sa.Column("daily_token_limit", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("profile_key"),
        )
        op.create_index("ix_ai_profiles_profile_key", "ai_profiles", ["profile_key"])

    if "ai_call_logs" not in tables:
        op.create_table(
            "ai_call_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("profile_id", sa.String(length=36), nullable=True),
            sa.Column("task_type", sa.String(length=64), nullable=False),
            sa.Column("target_type", sa.String(length=64), nullable=False),
            sa.Column("target_id", sa.String(length=36), nullable=True),
            sa.Column("request_hash", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["profile_id"], ["ai_profiles.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_call_logs_profile_id", "ai_call_logs", ["profile_id"])
        op.create_index("ix_ai_call_logs_task_type", "ai_call_logs", ["task_type"])
        op.create_index("ix_ai_call_logs_target_id", "ai_call_logs", ["target_id"])
        op.create_index("ix_ai_call_logs_request_hash", "ai_call_logs", ["request_hash"])
        op.create_index("ix_ai_call_logs_status", "ai_call_logs", ["status"])

    if "vulnerability_ai_enrichments" not in tables:
        op.create_table(
            "vulnerability_ai_enrichments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("vulnerability_id", sa.String(length=36), nullable=False),
            sa.Column("layer", sa.String(length=64), nullable=False),
            sa.Column("source_mode", sa.String(length=64), nullable=False),
            sa.Column("profile_id", sa.String(length=36), nullable=True),
            sa.Column("model", sa.String(length=128), nullable=True),
            sa.Column("input_hash", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=64), nullable=False),
            sa.Column("vendor", sa.String(length=255), nullable=True),
            sa.Column("product", sa.String(length=255), nullable=True),
            sa.Column("affected_versions", sa.Text(), nullable=True),
            sa.Column("fixed_versions", sa.Text(), nullable=True),
            sa.Column("remediation", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("evidence_json", sa.JSON(), nullable=False),
            sa.Column("source_urls_json", sa.JSON(), nullable=False),
            sa.Column("conflicts_json", sa.JSON(), nullable=False),
            sa.Column("raw_output_json", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("accepted_by", sa.String(length=36), nullable=True),
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejected_by", sa.String(length=36), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["profile_id"], ["ai_profiles.id"]),
            sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_vulnerability_ai_enrichments_vulnerability_id",
            "vulnerability_ai_enrichments",
            ["vulnerability_id"],
        )
        op.create_index(
            "ix_vulnerability_ai_enrichments_profile_id",
            "vulnerability_ai_enrichments",
            ["profile_id"],
        )
        op.create_index(
            "ix_vulnerability_ai_enrichments_layer",
            "vulnerability_ai_enrichments",
            ["layer"],
        )
        op.create_index(
            "ix_vulnerability_ai_enrichments_input_hash",
            "vulnerability_ai_enrichments",
            ["input_hash"],
        )
        op.create_index(
            "ix_vulnerability_ai_enrichments_status",
            "vulnerability_ai_enrichments",
            ["status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "vulnerability_ai_enrichments" in tables:
        op.drop_table("vulnerability_ai_enrichments")
    if "ai_call_logs" in tables:
        op.drop_table("ai_call_logs")
    if "ai_profiles" in tables:
        op.drop_table("ai_profiles")
