from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import (
    Asset,
    BusinessSystem,
    MatchResult,
    Person,
    ResponsibilityTeam,
    Vulnerability,
)


def _create_risk_with_ownership(
    db_session: Session,
    *,
    suffix: str,
) -> tuple[MatchResult, BusinessSystem, Person, ResponsibilityTeam]:
    team = ResponsibilityTeam(
        code=f"TEAM-{suffix}",
        name=f"责任团队 {suffix}",
        normalized_name=f"责任团队{suffix}".casefold(),
        status="active",
    )
    person = Person(
        employee_no=f"E-{suffix}",
        name=f"负责人 {suffix}",
        email=f"owner-{suffix.lower()}@example.com",
        team=team,
        status="active",
    )
    system = BusinessSystem(
        code=f"SYSTEM-{suffix}",
        name=f"业务系统 {suffix}",
        normalized_name=f"业务系统{suffix}".casefold(),
        responsible_person=person,
        status="active",
    )
    asset = Asset(
        hostname=f"asset-{suffix.lower()}.example.test",
        business_system_record=system,
        ownership_source="manual",
        ownership_updated_at=utcnow(),
        exposure_type="internal",
        criticality="high",
    )
    vulnerability = Vulnerability(
        canonical_id=f"CVE-2026-{suffix}",
        title=f"Ownership filter vulnerability {suffix}",
        product="nginx",
        severity_label="high",
        severity_cvss=8.1,
        fixed_versions="1.25.0",
    )
    result = MatchResult(
        risk_code=f"RISK-OWNERSHIP-{suffix}",
        vulnerability=vulnerability,
        asset=asset,
        status="affected",
        confidence=0.9,
        risk_score=8.1,
        risk_priority="high",
        risk_model_version="risk-v2.0",
        risk_factors_json=[],
        risk_explanation="Ownership filter test risk.",
        rule_version="v1",
    )
    db_session.add(result)
    db_session.commit()
    return result, system, person, team


def test_risk_queue_filters_and_detail_include_asset_ownership(
    client,
    db_session: Session,
) -> None:
    first, first_system, first_person, first_team = _create_risk_with_ownership(
        db_session,
        suffix="8101",
    )
    second, second_system, second_person, second_team = _create_risk_with_ownership(
        db_session,
        suffix="8102",
    )

    queue_response = client.get(
        "/api/v1/match-results/risk-queue",
        params={"handling_scope": "all"},
    )
    assert queue_response.status_code == 200
    queue_by_id = {item["id"]: item for item in queue_response.json()}
    assert {first.id, second.id}.issubset(queue_by_id)
    first_ownership = queue_by_id[first.id]["ownership"]
    assert first_ownership["status"] == "complete"
    assert first_ownership["source"] == "manual"
    assert first_ownership["updated_at"] is not None
    assert first_ownership["business_system"] == {
        "id": first_system.id,
        "code": first_system.code,
        "name": first_system.name,
        "status": "active",
    }
    assert first_ownership["responsible_person"] == {
        "id": first_person.id,
        "name": first_person.name,
        "email": first_person.email,
        "status": "active",
    }
    assert first_ownership["responsibility_team"] == {
        "id": first_team.id,
        "code": first_team.code,
        "name": first_team.name,
        "status": "active",
    }

    filter_cases = (
        ({"business_system_id": first_system.id}, first.id),
        ({"responsible_person_id": first_person.id}, first.id),
        ({"responsibility_team_id": first_team.id}, first.id),
        (
            {
                "business_system_id": second_system.id,
                "responsible_person_id": second_person.id,
                "responsibility_team_id": second_team.id,
            },
            second.id,
        ),
    )
    for params, expected_id in filter_cases:
        response = client.get(
            "/api/v1/match-results/risk-queue",
            params={**params, "handling_scope": "all"},
        )
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [expected_id]

    mismatched_response = client.get(
        "/api/v1/match-results/risk-queue",
        params={
            "business_system_id": first_system.id,
            "responsible_person_id": second_person.id,
            "handling_scope": "all",
        },
    )
    assert mismatched_response.status_code == 200
    assert mismatched_response.json() == []

    detail_response = client.get(f"/api/v1/match-results/{first.id}")
    assert detail_response.status_code == 200
    ownership = detail_response.json()["ownership"]
    assert ownership["business_system"]["id"] == first_system.id
    assert ownership["responsible_person"]["id"] == first_person.id
    assert ownership["responsibility_team"]["id"] == first_team.id


def test_risk_queue_ownership_projection_uses_bounded_queries(
    client,
    db_session: Session,
) -> None:
    for index in range(12):
        _create_risk_with_ownership(db_session, suffix=f"82{index:02d}")

    statements: list[str] = []

    def count_statement(*args) -> None:
        statements.append(str(args[2]))

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        response = client.get(
            "/api/v1/match-results/risk-queue",
            params={"handling_scope": "all", "limit": 50},
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)

    assert response.status_code == 200
    assert len(response.json()) == 12
    # Risk queue hydration uses a fixed set of select-in batches for risk context,
    # verification data, and the ownership chain. It must not grow per result row.
    assert len(statements) <= 13


def test_paged_risk_queue_summary_counts_full_filtered_result_set(
    client,
    db_session: Session,
) -> None:
    for index in range(35):
        result, _, _, _ = _create_risk_with_ownership(
            db_session,
            suffix=f"83{index:02d}",
        )
        if index < 12:
            result.risk_priority = "critical"
            result.risk_score = 9.5
            result.risk_factors_json = [
                {
                    "name": "stored",
                    "label": "Stored",
                    "value": 9.5,
                    "weight": 1.0,
                    "weighted_score": 9.5,
                }
            ]
        db_session.add(result)
    db_session.commit()

    response = client.get(
        "/api/v1/match-results/risk-queue",
        params={
            "paged": True,
            "handling_scope": "all",
            "offset": 0,
            "limit": 30,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 30
    assert payload["has_more"] is True
    assert payload["total"] == 35
    assert payload["critical_count"] == 12
    assert payload["unverified_count"] == 35
    assert payload["stale_asset_count"] == 35
