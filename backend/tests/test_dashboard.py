from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import (
    Asset,
    MatchResult,
    MatchResultHandlingRecord,
    RiskQueueEvent,
    Vulnerability,
)
from app.services.dashboard import get_dashboard_overview


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 7 if day > 5 else 8, day, hour, tzinfo=UTC)


def _add_risk(
    db: Session,
    *,
    index: int,
    entered_at: datetime,
    score: float,
    priority: str,
    handling_status: str = "unprocessed",
    closed_at: datetime | None = None,
) -> MatchResult:
    asset = Asset(
        hostname=f"host-{index}",
        display_name=f"Asset {index}",
        created_at=entered_at,
        updated_at=entered_at,
    )
    vulnerability = Vulnerability(
        canonical_id=f"CVE-2026-{9000 + index}",
        title=f"Dashboard vulnerability {index}",
        created_at=entered_at,
        updated_at=entered_at,
    )
    result = MatchResult(
        risk_code=f"RISK-DASH-{index}",
        risk_entered_at=entered_at,
        asset=asset,
        vulnerability=vulnerability,
        status="affected",
        confidence=0.9,
        risk_score=score,
        risk_priority=priority,
        handling_status=handling_status,
        handling_closed_at=closed_at,
        created_at=entered_at,
        updated_at=closed_at or entered_at,
    )
    result.risk_queue_events.append(
        RiskQueueEvent(
            event_type="entered",
            from_status="not_affected",
            to_status="affected",
            created_at=entered_at,
            updated_at=entered_at,
        )
    )
    if closed_at is not None:
        result.handling_records.append(
            MatchResultHandlingRecord(
                action="status_changed",
                from_status="unprocessed",
                to_status=handling_status,
                created_at=closed_at,
                updated_at=closed_at,
            )
        )
    db.add(result)
    return result


def test_dashboard_overview_uses_system_timezone_and_lifecycle_events(
    db_session: Session,
) -> None:
    _add_risk(
        db_session,
        index=1,
        entered_at=_dt(1, 1),
        score=9.7,
        priority="critical",
    )
    _add_risk(
        db_session,
        index=2,
        entered_at=_dt(27, 2),
        score=8.0,
        priority="high",
        handling_status="resolved",
        closed_at=_dt(2, 3),
    )
    _add_risk(
        db_session,
        index=3,
        entered_at=_dt(4, 4),
        score=8.5,
        priority="high",
    )
    _add_risk(
        db_session,
        index=4,
        entered_at=_dt(1, 5),
        score=5.0,
        priority="medium",
        handling_status="false_positive",
        closed_at=_dt(3, 6),
    )
    _add_risk(
        db_session,
        index=5,
        entered_at=_dt(28, 7),
        score=4.0,
        priority="low",
        handling_status="risk_accepted",
        closed_at=_dt(4, 8),
    )
    db_session.commit()

    overview = get_dashboard_overview(
        db_session,
        days=7,
        now=datetime(2026, 8, 5, 4, tzinfo=UTC),
        timezone_name="Asia/Shanghai",
    )

    assert overview.period.start_date.isoformat() == "2026-07-30"
    assert overview.period.end_date.isoformat() == "2026-08-05"
    assert overview.period.previous_start_date.isoformat() == "2026-07-23"
    assert overview.period.previous_end_date.isoformat() == "2026-07-29"
    assert overview.risk.current_total == 2
    assert overview.risk.period_new == 3
    assert overview.risk.previous_new == 2
    assert overview.risk.change_percent == 50.0
    assert overview.asset.current_total == 5
    assert overview.asset.period_new == 3
    assert overview.vulnerability.period_new == 3
    assert overview.closure.model_dump() == {
        "total": 3,
        "resolved": 1,
        "false_positive": 1,
        "risk_accepted": 1,
    }
    assert {item.key: item.count for item in overview.risk_priority_distribution} == {
        "critical": 1,
        "high": 1,
        "medium": 0,
        "low": 0,
        "none": 0,
    }
    assert {item.key: item.count for item in overview.handling_status_distribution} == {
        "unprocessed": 2,
        "notified": 0,
        "remediating": 0,
        "pending_review": 0,
    }
    assert overview.trend[-1].open_count == 2
    assert sum(point.new_count for point in overview.trend) == 3
    assert sum(point.closed_count for point in overview.trend) == 3
    assert [item.risk_code for item in overview.top_risks] == [
        "RISK-DASH-1",
        "RISK-DASH-3",
    ]


def test_dashboard_endpoint_validates_custom_date_pair(client) -> None:
    response = client.get("/api/v1/dashboard?start_date=2026-08-01")

    assert response.status_code == 400
    assert response.json()["detail"] == "start_date and end_date must be provided together"


def test_dashboard_endpoint_returns_empty_overview(client) -> None:
    response = client.get("/api/v1/dashboard?days=7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk"]["current_total"] == 0
    assert payload["asset"]["current_total"] == 0
    assert payload["vulnerability"]["current_total"] == 0
    assert payload["closure"]["total"] == 0
    assert len(payload["trend"]) == 7
