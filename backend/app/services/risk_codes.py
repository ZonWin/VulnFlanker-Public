from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import RiskCodeCounter


MAX_DAILY_RISK_CODES = 999_999
RISK_CODE_STATUSES = frozenset({"affected", "needs_review", "verified"})


class RiskCodeCapacityExceeded(RuntimeError):
    pass


def allocate_risk_code(
    db: Session,
    *,
    created_at: datetime | None = None,
) -> str:
    code_date = _utc_date(created_at or utcnow())
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert_statement = postgresql_insert(RiskCodeCounter)
    elif dialect == "sqlite":
        insert_statement = sqlite_insert(RiskCodeCounter)
    else:
        raise RuntimeError(f"Unsupported database dialect for risk code allocation: {dialect}")

    statement = (
        insert_statement.values(code_date=code_date, next_value=2)
        .on_conflict_do_update(
            index_elements=[RiskCodeCounter.code_date],
            set_={"next_value": RiskCodeCounter.next_value + 1},
        )
        .returning(RiskCodeCounter.next_value - 1)
    )
    sequence = int(db.execute(statement).scalar_one())
    if sequence > MAX_DAILY_RISK_CODES:
        raise RiskCodeCapacityExceeded(
            f"Risk code capacity exceeded for {code_date.isoformat()}"
        )
    return format_risk_code(code_date, sequence)


def format_risk_code(code_date: date, sequence: int) -> str:
    if sequence < 1 or sequence > MAX_DAILY_RISK_CODES:
        raise ValueError("Risk code sequence must be between 1 and 999999")
    return f"RISK-{code_date:%y%m%d}-{sequence:06d}"


def _utc_date(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()
