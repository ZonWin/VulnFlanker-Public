"""add risk business codes

Revision ID: f9c6a1d2e3b4
Revises: f8b4e2d6c701
Create Date: 2026-07-17 10:00:00.000000
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "f9c6a1d2e3b4"
down_revision = "f8b4e2d6c701"
branch_labels = None
depends_on = None

MAX_DAILY_SEQUENCE = 999_999


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "risk_code_counters" not in table_names:
        op.create_table(
            "risk_code_counters",
            sa.Column("code_date", sa.Date(), nullable=False),
            sa.Column("next_value", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("code_date"),
        )

    match_result_columns = {
        column["name"] for column in inspector.get_columns("match_results")
    }
    if "risk_code" not in match_result_columns:
        op.add_column(
            "match_results",
            sa.Column("risk_code", sa.String(length=32), nullable=True),
        )

    _backfill_risk_codes(bind)

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("match_results")}
    if "ix_match_results_risk_code" not in indexes:
        op.create_index(
            "ix_match_results_risk_code",
            "match_results",
            ["risk_code"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "match_results" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("match_results")}
        indexes = {index["name"] for index in inspector.get_indexes("match_results")}
        if "ix_match_results_risk_code" in indexes:
            op.drop_index("ix_match_results_risk_code", table_name="match_results")
        if "risk_code" in columns:
            op.drop_column("match_results", "risk_code")
    if "risk_code_counters" in sa.inspect(bind).get_table_names():
        op.drop_table("risk_code_counters")


def _backfill_risk_codes(bind) -> None:
    rows = bind.execute(
        sa.text(
            "SELECT id, created_at, risk_code FROM match_results "
            "WHERE status IN ('affected', 'needs_review', 'verified') "
            "ORDER BY created_at ASC, id ASC"
        )
    ).mappings()
    next_sequence_by_date: dict[date, int] = defaultdict(lambda: 1)

    for row in rows:
        code_date = _as_utc_date(row["created_at"])
        sequence = next_sequence_by_date[code_date]
        if sequence > MAX_DAILY_SEQUENCE:
            raise RuntimeError(
                f"More than {MAX_DAILY_SEQUENCE} risk records exist on {code_date}"
            )
        if not row["risk_code"]:
            bind.execute(
                sa.text(
                    "UPDATE match_results SET risk_code = :risk_code WHERE id = :id"
                ),
                {
                    "id": row["id"],
                    "risk_code": f"RISK-{code_date:%y%m%d}-{sequence:06d}",
                },
            )
        next_sequence_by_date[code_date] = sequence + 1

    for code_date, next_value in next_sequence_by_date.items():
        bind.execute(
            sa.text(
                "INSERT INTO risk_code_counters (code_date, next_value) "
                "VALUES (:code_date, :next_value) "
                "ON CONFLICT (code_date) DO UPDATE SET next_value = :next_value"
            ),
            {"code_date": code_date, "next_value": next_value},
        )


def _as_utc_date(value: datetime | str) -> date:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()
