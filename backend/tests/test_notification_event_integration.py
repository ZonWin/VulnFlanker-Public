from __future__ import annotations

from sqlalchemy import func, select

from app.db.base import utcnow
from app.db.models import (
    AdminNotification,
    Asset,
    BusinessSystem,
    EmailDelivery,
    MatchResult,
    MatchResultHandlingRecord,
    Person,
    ResponsibilityTeam,
    SystemEvent,
    Vulnerability,
)
from app.services.email_alerts import get_email_settings
from app.services.intel_tracking import complete_collection_run, create_collection_run
from app.services.risk_notifications import (
    RiskStateSnapshot,
    classify_risk_change,
    process_risk_evaluation_changes,
)


def _owned_result(
    db_session,
    *,
    suffix: str,
    person: Person | None = None,
    priority: str = "high",
) -> MatchResult:
    if person is None:
        team = ResponsibilityTeam(
            code=f"TEAM-{suffix}",
            name=f"Team {suffix}",
            normalized_name=f"team-{suffix}",
            status="active",
        )
        person = Person(
            employee_no=f"EMP-{suffix}",
            name=f"Owner {suffix}",
            email=f"owner-{suffix}@example.test",
            team=team,
            status="active",
        )
    system = BusinessSystem(
        code=f"SYS-{suffix}",
        name=f"System {suffix}",
        normalized_name=f"system-{suffix}",
        responsible_person=person,
        status="active",
    )
    asset = Asset(
        hostname=f"asset-{suffix}.example.test",
        business_system_record=system,
        ownership_source="manual",
        ownership_updated_at=utcnow(),
        exposure_type="internal",
        criticality="high",
    )
    vulnerability = Vulnerability(
        canonical_id=f"CVE-2026-{suffix}",
        title=f"Risk {suffix}",
        product="nginx",
        severity_label="high",
        severity_cvss=8.8,
        affected_versions="< 1.25.0",
        fixed_versions="1.25.0",
    )
    result = MatchResult(
        risk_code=f"RISK-{suffix}",
        vulnerability=vulnerability,
        asset=asset,
        status="affected",
        confidence=0.9,
        risk_score=8.8,
        risk_priority=priority,
        risk_model_version="risk-v2.0",
        risk_factors_json=[],
        rule_version="v1",
    )
    db_session.add(result)
    db_session.commit()
    return result


def _enable_automatic_email(db_session, *, threshold: str = "high") -> None:
    settings = get_email_settings(db_session)
    settings.enabled = True
    settings.automatic_enabled = True
    settings.risk_threshold = threshold
    settings.smtp_host = "smtp.example.test"
    settings.sender_email = "alerts@example.test"
    db_session.add(settings)
    db_session.commit()


def test_intel_collection_terminal_event_is_idempotent(db_session) -> None:
    run = create_collection_run(
        db_session,
        source_name="watchvuln",
        trigger_type="manual",
    )
    complete_collection_run(
        db_session,
        run,
        fetched_count=10,
        stored_count=8,
        processed_count=7,
        skipped_count=1,
    )
    complete_collection_run(
        db_session,
        run,
        fetched_count=10,
        stored_count=8,
        processed_count=7,
        skipped_count=1,
    )
    db_session.commit()

    events = db_session.scalars(select(SystemEvent)).all()
    assert len(events) == 1
    assert events[0].event_key == f"intel.collection:{run.id}"
    assert events[0].details_json["processed_count"] == 7
    assert db_session.scalar(select(func.count(AdminNotification.id))) == 1


def test_risk_evaluation_creates_one_notification_and_groups_email_by_owner(
    db_session,
) -> None:
    _enable_automatic_email(db_session, threshold="high")
    first = _owned_result(db_session, suffix="9101", priority="high")
    owner = first.asset.business_system_record.responsible_person
    assert owner is not None
    second = _owned_result(
        db_session,
        suffix="9102",
        person=owner,
        priority="critical",
    )
    changes = [
        classify_risk_change(
            first,
            RiskStateSnapshot(True, "affected", "medium", "unprocessed", None),
        ),
        classify_risk_change(
            second,
            RiskStateSnapshot(False, "not_evaluated", "none", "unprocessed", None),
        ),
    ]
    assert all(change is not None for change in changes)

    outcome = process_risk_evaluation_changes(
        db_session,
        changes=[change for change in changes if change is not None],
        trigger_type="automatic",
        evaluation_event_id="evaluation-grouped",
    )
    db_session.commit()

    assert outcome.system_event is not None
    assert outcome.system_event.details_json["upgraded_count"] == 1
    assert outcome.system_event.details_json["new_count"] == 1
    assert db_session.scalar(select(func.count(AdminNotification.id))) == 1
    deliveries = db_session.scalars(select(EmailDelivery)).all()
    assert len(deliveries) == 1
    assert deliveries[0].status == "queued"
    assert deliveries[0].recipient_person_id == owner.id
    assert deliveries[0].risk_count == 2
    assert set(deliveries[0].match_result_ids_json) == {first.id, second.id}


def test_priority_upgrade_above_existing_threshold_only_notifies_in_app(
    db_session,
) -> None:
    _enable_automatic_email(db_session, threshold="high")
    result = _owned_result(db_session, suffix="9201", priority="critical")
    change = classify_risk_change(
        result,
        RiskStateSnapshot(True, "affected", "high", "unprocessed", None),
    )
    assert change is not None and change.kind == "upgraded"

    process_risk_evaluation_changes(
        db_session,
        changes=[change],
        trigger_type="automatic",
        evaluation_event_id="evaluation-no-repeat-email",
    )
    db_session.commit()

    assert db_session.scalar(select(func.count(SystemEvent.id))) == 1
    assert db_session.scalar(select(func.count(EmailDelivery.id))) == 0


def test_automatic_switch_off_keeps_risk_notification_without_email(db_session) -> None:
    settings = get_email_settings(db_session)
    settings.enabled = True
    settings.automatic_enabled = False
    settings.risk_threshold = "high"
    settings.smtp_host = "smtp.example.test"
    settings.sender_email = "alerts@example.test"
    db_session.add(settings)
    db_session.commit()
    result = _owned_result(db_session, suffix="9251", priority="high")
    change = classify_risk_change(
        result,
        RiskStateSnapshot(False, "not_evaluated", "none", "unprocessed", None),
    )
    assert change is not None

    process_risk_evaluation_changes(
        db_session,
        changes=[change],
        trigger_type="automatic",
        evaluation_event_id="evaluation-auto-off",
    )
    db_session.commit()

    assert db_session.scalar(select(func.count(SystemEvent.id))) == 1
    assert db_session.scalar(select(func.count(EmailDelivery.id))) == 0


def test_closed_risk_reappearance_reopens_and_can_alert(db_session) -> None:
    _enable_automatic_email(db_session, threshold="high")
    result = _owned_result(db_session, suffix="9301", priority="high")
    closed_at = utcnow()
    result.handling_status = "resolved"
    result.handling_closed_at = closed_at
    db_session.add(result)
    db_session.commit()
    previous = RiskStateSnapshot(
        True,
        "not_affected",
        "none",
        "resolved",
        closed_at,
    )
    change = classify_risk_change(result, previous)
    assert change is not None and change.kind == "reappeared"

    process_risk_evaluation_changes(
        db_session,
        changes=[change],
        trigger_type="automatic",
        evaluation_event_id="evaluation-reappeared",
    )
    db_session.commit()

    assert result.handling_status == "unprocessed"
    assert result.handling_closed_at is None
    record = db_session.scalar(
        select(MatchResultHandlingRecord).where(
            MatchResultHandlingRecord.match_result_id == result.id
        )
    )
    assert record is not None
    assert record.action == "risk_reappeared"
    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None and delivery.status == "queued"


def test_missing_owner_email_creates_skipped_log_without_rollback(db_session) -> None:
    _enable_automatic_email(db_session, threshold="high")
    result = _owned_result(db_session, suffix="9401", priority="high")
    person = result.asset.business_system_record.responsible_person
    assert person is not None
    person.email = None
    db_session.add(person)
    db_session.commit()
    change = classify_risk_change(
        result,
        RiskStateSnapshot(False, "not_evaluated", "none", "unprocessed", None),
    )
    assert change is not None

    process_risk_evaluation_changes(
        db_session,
        changes=[change],
        trigger_type="automatic",
        evaluation_event_id="evaluation-no-email",
    )
    db_session.commit()

    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None
    assert delivery.status == "skipped"
    assert delivery.skip_reason == "missing_recipient_email"
    assert db_session.get(MatchResult, result.id) is not None


def test_manual_risk_email_allows_repeat_and_respects_threshold(
    client,
    db_session,
    monkeypatch,
) -> None:
    _enable_automatic_email(db_session, threshold="high")
    result = _owned_result(db_session, suffix="9501", priority="high")
    monkeypatch.setattr(
        "app.services.risk_notifications.enqueue_email_delivery",
        lambda _delivery_id: True,
    )

    first = client.post(f"/api/v1/match-results/{result.id}/email-alert")
    second = client.post(f"/api/v1/match-results/{result.id}/email-alert")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["delivery_id"] != second.json()["delivery_id"]
    assert db_session.scalar(select(func.count(EmailDelivery.id))) == 2

    result.risk_priority = "medium"
    db_session.add(result)
    db_session.commit()
    skipped = client.post(f"/api/v1/match-results/{result.id}/email-alert")
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"
    latest = db_session.scalar(
        select(EmailDelivery).order_by(EmailDelivery.created_at.desc())
    )
    assert latest is not None and latest.skip_reason == "below_threshold"


def test_global_email_switch_blocks_manual_test_and_resend(
    client,
    db_session,
) -> None:
    result = _owned_result(db_session, suffix="9551", priority="high")
    settings = get_email_settings(db_session)
    assert settings.enabled is False
    failed = EmailDelivery(
        trigger_type="manual",
        status="failed",
        recipient_email="owner@example.test",
        subject="Failed",
        text_body="Failed",
        html_body="<p>Failed</p>",
        match_result_ids_json=[result.id],
        context_json={},
    )
    db_session.add(failed)
    db_session.commit()

    manual = client.post(f"/api/v1/match-results/{result.id}/email-alert")
    test_email = client.post(
        "/api/v1/email-settings/test",
        json={"recipient_email": "test@example.test"},
    )
    resend = client.post(f"/api/v1/email-deliveries/{failed.id}/resend")
    assert manual.status_code == 400
    assert test_email.status_code == 400
    assert resend.status_code == 400
    assert "disabled" in manual.json()["detail"].lower()


def test_asset_snapshot_creates_only_one_asset_event(client, db_session) -> None:
    payload = {
        "agent_id": "agent-notification-001",
        "agent_version": "0.1.0",
        "hostname": "notify-asset.example.test",
        "primary_ip": "10.0.0.10",
        "platform": "linux",
        "os_family": "ubuntu",
        "os_version": "24.04",
        "kernel_version": "6.8.0",
        "architecture": "x86_64",
        "environment_type": "production",
        "exposure_type": "internal",
        "criticality": "medium",
        "allow_auto_verify": False,
        "components": [],
        "exposures": [],
        "collected_at": "2026-08-05T10:00:00Z",
    }
    first = client.post("/api/v1/agents/snapshots", json=payload)
    assert first.status_code == 202, first.text
    payload["collected_at"] = "2026-08-05T10:05:00Z"
    second = client.post("/api/v1/agents/snapshots", json=payload)
    assert second.status_code == 202, second.text

    events = db_session.scalars(
        select(SystemEvent).where(SystemEvent.category == "asset")
    ).all()
    assert len(events) == 1
    assert events[0].details_json["created_count"] == 1
