"""add dashboard risk lifecycle

Revision ID: d8e7f6a5b4c3
Revises: f1a2b3c4d5e6
Create Date: 2026-08-05 00:00:00.000000
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision = "d8e7f6a5b4c3"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "match_results",
        sa.Column("risk_entered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_match_results_risk_entered_at",
        "match_results",
        ["risk_entered_at"],
        unique=False,
    )
    op.create_table(
        "risk_queue_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("match_result_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('entered', 'exited')",
            name="ck_risk_queue_events_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["match_result_id"],
            ["match_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_risk_queue_events_event_type",
        "risk_queue_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_risk_queue_events_match_result_id",
        "risk_queue_events",
        ["match_result_id"],
        unique=False,
    )

    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT id, status, created_at, updated_at FROM match_results "
                "WHERE risk_code IS NOT NULL"
            )
        ).mappings()
    )
    if not rows:
        return
    bind.execute(
        sa.text(
            "UPDATE match_results SET risk_entered_at = created_at "
            "WHERE risk_code IS NOT NULL AND risk_entered_at IS NULL"
        )
    )
    event_table = sa.table(
        "risk_queue_events",
        sa.column("id", sa.String),
        sa.column("match_result_id", sa.String),
        sa.column("event_type", sa.String),
        sa.column("from_status", sa.String),
        sa.column("to_status", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    queue_statuses = {"verified", "affected", "needs_review"}
    events: list[dict[str, object]] = []
    for row in rows:
        events.append(
            {
                "id": str(uuid4()),
                "match_result_id": row["id"],
                "event_type": "entered",
                "from_status": None,
                "to_status": "legacy_risk",
                "created_at": row["created_at"],
                "updated_at": row["created_at"],
            }
        )
        if row["status"] not in queue_statuses:
            events.append(
                {
                    "id": str(uuid4()),
                    "match_result_id": row["id"],
                    "event_type": "exited",
                    "from_status": "legacy_risk",
                    "to_status": row["status"],
                    "created_at": row["updated_at"],
                    "updated_at": row["updated_at"],
                }
            )
    op.bulk_insert(event_table, events)


def downgrade() -> None:
    op.drop_index("ix_risk_queue_events_match_result_id", table_name="risk_queue_events")
    op.drop_index("ix_risk_queue_events_event_type", table_name="risk_queue_events")
    op.drop_table("risk_queue_events")
    op.drop_index("ix_match_results_risk_entered_at", table_name="match_results")
    op.drop_column("match_results", "risk_entered_at")
