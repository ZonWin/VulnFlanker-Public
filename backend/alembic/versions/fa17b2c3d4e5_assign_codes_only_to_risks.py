"""assign business codes only to actual risks

Revision ID: fa17b2c3d4e5
Revises: f9c6a1d2e3b4
Create Date: 2026-07-17 10:25:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "fa17b2c3d4e5"
down_revision = "f9c6a1d2e3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "match_results",
        "risk_code",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.execute(
        sa.text(
            "UPDATE match_results SET risk_code = NULL "
            "WHERE status NOT IN ('affected', 'needs_review', 'verified')"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, created_at FROM match_results "
            "WHERE risk_code IS NULL ORDER BY created_at ASC, id ASC"
        )
    ).mappings()
    for row in rows:
        code_date = _as_utc_datetime(row["created_at"]).date()
        sequence = bind.execute(
            sa.text(
                "INSERT INTO risk_code_counters (code_date, next_value) "
                "VALUES (:code_date, 2) "
                "ON CONFLICT (code_date) DO UPDATE "
                "SET next_value = risk_code_counters.next_value + 1 "
                "RETURNING next_value - 1"
            ),
            {"code_date": code_date},
        ).scalar_one()
        bind.execute(
            sa.text(
                "UPDATE match_results SET risk_code = :risk_code WHERE id = :id"
            ),
            {
                "id": row["id"],
                "risk_code": f"RISK-{code_date:%y%m%d}-{int(sequence):06d}",
            },
        )
    op.alter_column(
        "match_results",
        "risk_code",
        existing_type=sa.String(length=32),
        nullable=False,
    )


def _as_utc_datetime(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
