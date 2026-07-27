from datetime import date, datetime, timezone

import pytest

from app.services.risk_codes import allocate_risk_code, format_risk_code


def test_allocates_six_digit_daily_sequences(db_session) -> None:
    created_at = datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc)

    assert allocate_risk_code(db_session, created_at=created_at) == (
        "RISK-260717-000001"
    )
    assert allocate_risk_code(db_session, created_at=created_at) == (
        "RISK-260717-000002"
    )


def test_daily_sequence_resets(db_session) -> None:
    assert allocate_risk_code(
        db_session,
        created_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
    ) == "RISK-260717-000001"
    assert allocate_risk_code(
        db_session,
        created_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
    ) == "RISK-260718-000001"


def test_rejects_sequence_beyond_six_digits() -> None:
    with pytest.raises(ValueError, match="999999"):
        format_risk_code(date(2026, 7, 17), 1_000_000)
