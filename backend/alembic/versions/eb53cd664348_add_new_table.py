"""add new table

Revision ID: eb53cd664348
Revises: 
Create Date: 2026-05-02 19:34:57.944363
"""
import sqlalchemy as sa
from alembic import op



# revision identifiers, used by Alembic.
revision = 'eb53cd664348'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("primary_ip", sa.String(length=64), nullable=True),
        sa.Column("os_family", sa.String(length=64), nullable=True),
        sa.Column("os_version", sa.String(length=128), nullable=True),
        sa.Column("kernel_version", sa.String(length=128), nullable=True),
        sa.Column("environment_type", sa.String(length=32), nullable=False),
        sa.Column("exposure_type", sa.String(length=32), nullable=False),
        sa.Column("business_system", sa.String(length=255), nullable=True),
        sa.Column("owner_team", sa.String(length=255), nullable=True),
        sa.Column("owner_person", sa.String(length=255), nullable=True),
        sa.Column("criticality", sa.String(length=32), nullable=False),
        sa.Column("allow_auto_verify", sa.Boolean(), nullable=False),
        sa.Column("allow_auto_remediate", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assets_hostname"), "assets", ["hostname"], unique=False)

    op.create_table(
        "vulnerabilities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("canonical_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("vendor", sa.String(length=255), nullable=True),
        sa.Column("product", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity_label", sa.String(length=64), nullable=True),
        sa.Column("severity_cvss", sa.Float(), nullable=True),
        sa.Column("epss", sa.Float(), nullable=True),
        sa.Column("kev_status", sa.Boolean(), nullable=False),
        sa.Column("kev_date_added", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kev_due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("known_ransomware_campaign_use", sa.String(length=64), nullable=True),
        sa.Column("poc_status", sa.Boolean(), nullable=False),
        sa.Column("wild_exploitation_status", sa.Boolean(), nullable=False),
        sa.Column("affected_versions", sa.Text(), nullable=True),
        sa.Column("fixed_versions", sa.Text(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_id"),
    )
    op.create_index(
        op.f("ix_vulnerabilities_canonical_id"),
        "vulnerabilities",
        ["canonical_id"],
        unique=True,
    )

    op.create_table(
        "intel_raw_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("external_key", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("vulnerability_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "payload_hash",
            name="uq_intel_raw_events_provider_payload_hash",
        ),
    )
    op.create_index(
        op.f("ix_intel_raw_events_event_type"),
        "intel_raw_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_intel_raw_events_external_key"),
        "intel_raw_events",
        ["external_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_intel_raw_events_processing_status"),
        "intel_raw_events",
        ["processing_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_intel_raw_events_provider"),
        "intel_raw_events",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_intel_raw_events_vulnerability_id"),
        "intel_raw_events",
        ["vulnerability_id"],
        unique=False,
    )

    op.create_table(
        "asset_components",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("component_name", sa.String(length=255), nullable=False),
        sa.Column("component_type", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("install_path", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_asset_components_asset_id"),
        "asset_components",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_components_component_name"),
        "asset_components",
        ["component_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_components_component_type"),
        "asset_components",
        ["component_type"],
        unique=False,
    )

    op.create_table(
        "match_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vulnerability_id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_match_results_asset_id"),
        "match_results",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_match_results_vulnerability_id"),
        "match_results",
        ["vulnerability_id"],
        unique=False,
    )

    op.create_table(
        "vulnerability_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vulnerability_id", sa.String(length=36), nullable=False),
        sa.Column("raw_event_id", sa.String(length=36), nullable=True),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity_raw", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("references_json", sa.JSON(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("last_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["intel_raw_events.id"]),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_name",
            "external_id",
            name="uq_vulnerability_sources_name_external_id",
        ),
    )
    op.create_index(
        op.f("ix_vulnerability_sources_raw_event_id"),
        "vulnerability_sources",
        ["raw_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vulnerability_sources_source_name"),
        "vulnerability_sources",
        ["source_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vulnerability_sources_vulnerability_id"),
        "vulnerability_sources",
        ["vulnerability_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_vulnerability_sources_vulnerability_id"), table_name="vulnerability_sources")
    op.drop_index(op.f("ix_vulnerability_sources_source_name"), table_name="vulnerability_sources")
    op.drop_index(op.f("ix_vulnerability_sources_raw_event_id"), table_name="vulnerability_sources")
    op.drop_table("vulnerability_sources")

    op.drop_index(op.f("ix_match_results_vulnerability_id"), table_name="match_results")
    op.drop_index(op.f("ix_match_results_asset_id"), table_name="match_results")
    op.drop_table("match_results")

    op.drop_index(op.f("ix_asset_components_component_type"), table_name="asset_components")
    op.drop_index(op.f("ix_asset_components_component_name"), table_name="asset_components")
    op.drop_index(op.f("ix_asset_components_asset_id"), table_name="asset_components")
    op.drop_table("asset_components")

    op.drop_index(op.f("ix_intel_raw_events_vulnerability_id"), table_name="intel_raw_events")
    op.drop_index(op.f("ix_intel_raw_events_provider"), table_name="intel_raw_events")
    op.drop_index(op.f("ix_intel_raw_events_processing_status"), table_name="intel_raw_events")
    op.drop_index(op.f("ix_intel_raw_events_external_key"), table_name="intel_raw_events")
    op.drop_index(op.f("ix_intel_raw_events_event_type"), table_name="intel_raw_events")
    op.drop_table("intel_raw_events")

    op.drop_index(op.f("ix_vulnerabilities_canonical_id"), table_name="vulnerabilities")
    op.drop_table("vulnerabilities")

    op.drop_index(op.f("ix_assets_hostname"), table_name="assets")
    op.drop_table("assets")
