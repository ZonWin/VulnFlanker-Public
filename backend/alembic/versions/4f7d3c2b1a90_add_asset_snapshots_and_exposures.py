"""add asset snapshots and exposures

Revision ID: 4f7d3c2b1a90
Revises: 8a6d4c8b0f8d
Create Date: 2026-05-05 23:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "4f7d3c2b1a90"
down_revision = "8a6d4c8b0f8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    asset_columns = {column["name"] for column in inspector.get_columns("assets")}
    for column_name, column in (
        ("agent_id", sa.Column("agent_id", sa.String(length=128), nullable=True)),
        ("platform", sa.Column("platform", sa.String(length=64), nullable=True)),
        ("architecture", sa.Column("architecture", sa.String(length=64), nullable=True)),
        ("last_seen_at", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)),
    ):
        if column_name not in asset_columns:
            op.add_column("assets", column)

    asset_indexes = {index["name"] for index in inspector.get_indexes("assets")}
    if "ix_assets_agent_id" not in asset_indexes:
        op.create_index("ix_assets_agent_id", "assets", ["agent_id"], unique=True)

    tables = set(inspector.get_table_names())
    if "asset_exposures" not in tables:
        op.create_table(
            "asset_exposures",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("asset_id", sa.String(length=36), nullable=False),
            sa.Column("exposure_kind", sa.String(length=64), nullable=False),
            sa.Column("address", sa.String(length=128), nullable=True),
            sa.Column("port", sa.Integer(), nullable=True),
            sa.Column("protocol", sa.String(length=16), nullable=False),
            sa.Column("service_name", sa.String(length=255), nullable=True),
            sa.Column("product", sa.String(length=255), nullable=True),
            sa.Column("version", sa.String(length=128), nullable=True),
            sa.Column("state", sa.String(length=32), nullable=False),
            sa.Column("is_public", sa.Boolean(), nullable=False),
            sa.Column("banner", sa.Text(), nullable=True),
            sa.Column("evidence_ref", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_asset_exposures_asset_id"),
            "asset_exposures",
            ["asset_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_asset_exposures_exposure_kind"),
            "asset_exposures",
            ["exposure_kind"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "asset_snapshots" not in tables:
        op.create_table(
            "asset_snapshots",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("asset_id", sa.String(length=36), nullable=False),
            sa.Column("agent_id", sa.String(length=128), nullable=False),
            sa.Column("agent_version", sa.String(length=64), nullable=True),
            sa.Column("platform", sa.String(length=64), nullable=True),
            sa.Column("hostname", sa.String(length=255), nullable=False),
            sa.Column("primary_ip", sa.String(length=64), nullable=True),
            sa.Column("os_family", sa.String(length=64), nullable=True),
            sa.Column("os_version", sa.String(length=128), nullable=True),
            sa.Column("kernel_version", sa.String(length=128), nullable=True),
            sa.Column("architecture", sa.String(length=64), nullable=True),
            sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
            sa.Column("component_count", sa.Integer(), nullable=False),
            sa.Column("exposure_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "asset_id",
                "payload_hash",
                name="uq_asset_snapshots_asset_payload_hash",
            ),
        )
        op.create_index(
            op.f("ix_asset_snapshots_agent_id"),
            "asset_snapshots",
            ["agent_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_asset_snapshots_asset_id"),
            "asset_snapshots",
            ["asset_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "asset_snapshots" in tables:
        op.drop_table("asset_snapshots")

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "asset_exposures" in tables:
        op.drop_table("asset_exposures")

    asset_columns = {column["name"] for column in inspector.get_columns("assets")}
    asset_indexes = {index["name"] for index in inspector.get_indexes("assets")}
    if "ix_assets_agent_id" in asset_indexes:
        op.drop_index("ix_assets_agent_id", table_name="assets")

    for column_name in ("last_seen_at", "architecture", "platform", "agent_id"):
        if column_name in asset_columns:
            op.drop_column("assets", column_name)
