"""add intel schema incrementally

Revision ID: 8a6d4c8b0f8d
Revises: eb53cd664348
Create Date: 2026-05-02 22:15:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "8a6d4c8b0f8d"
down_revision = "eb53cd664348"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    vulnerability_columns = {column["name"] for column in inspector.get_columns("vulnerabilities")}
    for column_name, column in (
        ("severity_label", sa.Column("severity_label", sa.String(length=64), nullable=True)),
        ("kev_date_added", sa.Column("kev_date_added", sa.DateTime(timezone=True), nullable=True)),
        ("kev_due_date", sa.Column("kev_due_date", sa.DateTime(timezone=True), nullable=True)),
        (
            "known_ransomware_campaign_use",
            sa.Column("known_ransomware_campaign_use", sa.String(length=64), nullable=True),
        ),
        ("remediation", sa.Column("remediation", sa.Text(), nullable=True)),
        ("published_at", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)),
        ("notes", sa.Column("notes", sa.Text(), nullable=True)),
    ):
        if column_name not in vulnerability_columns:
            op.add_column("vulnerabilities", column)

    tables = set(inspector.get_table_names())
    if "intel_raw_events" not in tables:
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

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "vulnerability_sources" not in tables:
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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "vulnerability_sources" in tables:
        op.drop_index(op.f("ix_vulnerability_sources_vulnerability_id"), table_name="vulnerability_sources")
        op.drop_index(op.f("ix_vulnerability_sources_source_name"), table_name="vulnerability_sources")
        op.drop_index(op.f("ix_vulnerability_sources_raw_event_id"), table_name="vulnerability_sources")
        op.drop_table("vulnerability_sources")

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "intel_raw_events" in tables:
        op.drop_index(op.f("ix_intel_raw_events_vulnerability_id"), table_name="intel_raw_events")
        op.drop_index(op.f("ix_intel_raw_events_provider"), table_name="intel_raw_events")
        op.drop_index(op.f("ix_intel_raw_events_processing_status"), table_name="intel_raw_events")
        op.drop_index(op.f("ix_intel_raw_events_external_key"), table_name="intel_raw_events")
        op.drop_index(op.f("ix_intel_raw_events_event_type"), table_name="intel_raw_events")
        op.drop_table("intel_raw_events")

    inspector = sa.inspect(bind)
    vulnerability_columns = {column["name"] for column in inspector.get_columns("vulnerabilities")}
    for column_name in (
        "notes",
        "published_at",
        "remediation",
        "known_ransomware_campaign_use",
        "kev_due_date",
        "kev_date_added",
        "severity_label",
    ):
        if column_name in vulnerability_columns:
            op.drop_column("vulnerabilities", column_name)
