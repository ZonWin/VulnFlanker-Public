"""add asset firewall inventory

Revision ID: 6b2f4c8e1a73
Revises: 0d7e2a9c4f61
Create Date: 2026-07-20 19:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "6b2f4c8e1a73"
down_revision = "0d7e2a9c4f61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_firewalls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("backend", sa.String(length=32), nullable=True),
        sa.Column("managed_by", sa.String(length=32), nullable=True),
        sa.Column("effective", sa.Boolean(), nullable=False),
        sa.Column("installed", sa.Boolean(), nullable=False),
        sa.Column("runtime_state", sa.String(length=32), nullable=False),
        sa.Column("service_enabled", sa.Boolean(), nullable=True),
        sa.Column("collection_status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("runtime_rule_count", sa.Integer(), nullable=False),
        sa.Column("permanent_rule_count", sa.Integer(), nullable=False),
        sa.Column("raw_runtime", sa.Text(), nullable=True),
        sa.Column("raw_permanent", sa.Text(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "engine IN ('firewalld', 'ufw', 'iptables', 'nftables')",
            name="ck_asset_firewalls_engine",
        ),
        sa.CheckConstraint(
            "role IN ('manager', 'backend', 'compatibility', 'standalone')",
            name="ck_asset_firewalls_role",
        ),
        sa.CheckConstraint(
            "runtime_state IN ('active', 'inactive', 'configured', 'unknown')",
            name="ck_asset_firewalls_runtime_state",
        ),
        sa.CheckConstraint(
            "collection_status IN ('success', 'partial', 'unsupported', "
            "'permission_denied', 'timeout', 'error')",
            name="ck_asset_firewalls_collection_status",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_id",
            "engine",
            name="uq_asset_firewalls_asset_engine",
        ),
    )
    op.create_index(
        op.f("ix_asset_firewalls_asset_id"),
        "asset_firewalls",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_firewalls_engine"),
        "asset_firewalls",
        ["engine"],
        unique=False,
    )

    op.create_table(
        "asset_firewall_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("firewall_id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("family", sa.String(length=16), nullable=True),
        sa.Column("table_name", sa.String(length=128), nullable=True),
        sa.Column("chain_name", sa.String(length=128), nullable=True),
        sa.Column("zone", sa.String(length=128), nullable=True),
        sa.Column("rule_order", sa.Integer(), nullable=False),
        sa.Column("rule_kind", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=True),
        sa.Column("protocol", sa.String(length=32), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("destination", sa.Text(), nullable=True),
        sa.Column("source_port", sa.String(length=128), nullable=True),
        sa.Column("destination_port", sa.String(length=128), nullable=True),
        sa.Column("in_interface", sa.String(length=128), nullable=True),
        sa.Column("out_interface", sa.String(length=128), nullable=True),
        sa.Column("state_match", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("raw_rule", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope IN ('runtime', 'permanent')",
            name="ck_asset_firewall_rules_scope",
        ),
        sa.ForeignKeyConstraint(
            ["firewall_id"],
            ["asset_firewalls.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_asset_firewall_rules_firewall_id"),
        "asset_firewall_rules",
        ["firewall_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_firewall_rules_scope"),
        "asset_firewall_rules",
        ["scope"],
        unique=False,
    )

    op.add_column(
        "asset_snapshots",
        sa.Column("firewall_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "asset_snapshots",
        sa.Column(
            "firewall_rule_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.alter_column("asset_snapshots", "firewall_count", server_default=None)
    op.alter_column("asset_snapshots", "firewall_rule_count", server_default=None)


def downgrade() -> None:
    op.drop_column("asset_snapshots", "firewall_rule_count")
    op.drop_column("asset_snapshots", "firewall_count")
    op.drop_index(
        op.f("ix_asset_firewall_rules_scope"),
        table_name="asset_firewall_rules",
    )
    op.drop_index(
        op.f("ix_asset_firewall_rules_firewall_id"),
        table_name="asset_firewall_rules",
    )
    op.drop_table("asset_firewall_rules")
    op.drop_index(op.f("ix_asset_firewalls_engine"), table_name="asset_firewalls")
    op.drop_index(op.f("ix_asset_firewalls_asset_id"), table_name="asset_firewalls")
    op.drop_table("asset_firewalls")
