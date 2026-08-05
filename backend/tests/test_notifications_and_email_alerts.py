from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.db.base import utcnow
from app.db.models import AuditLog, EmailDelivery, EmailSettings
from app.services import email_alerts
from app.services.email_alerts import (
    create_email_delivery,
    preview_email_templates,
    send_email_delivery,
)
from app.services.notifications import create_system_event
from app.services.secret_crypto import encrypt_secret


def test_notification_api_read_state_and_long_term_history(client, db_session) -> None:
    event = create_system_event(
        db_session,
        event_key="asset.created:test-asset",
        category="asset",
        event_type="asset_created",
        level="success",
        title="新增资产",
        summary="本次新增 1 台资产。",
        details={"asset_ids": ["test-asset"], "created_count": 1},
        target_type="asset",
        target_id="test-asset",
    )
    duplicate = create_system_event(
        db_session,
        event_key="asset.created:test-asset",
        category="asset",
        event_type="asset_created",
        level="success",
        title="不会重复",
        summary="不会重复",
    )
    db_session.commit()
    assert duplicate.id == event.id

    page = client.get("/api/v1/notifications").json()
    assert page["total"] == 1
    notification = page["items"][0]
    assert notification["event"]["event_key"] == "asset.created:test-asset"
    assert client.get("/api/v1/notifications/unread-count").json() == {"count": 1}

    marked = client.post(f"/api/v1/notifications/{notification['id']}/read")
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None
    assert client.get("/api/v1/notifications/unread-count").json() == {"count": 0}

    history = client.get("/api/v1/notifications/history?category=asset").json()
    assert history["total"] == 1
    assert history["items"][0]["details"]["created_count"] == 1


def test_expired_notification_is_hidden_but_history_remains(client, db_session) -> None:
    event = create_system_event(
        db_session,
        event_key="intel.collection:test-run",
        category="intel",
        event_type="intel_collection_completed",
        level="success",
        title="情报采集完成",
        summary="任务完成。",
        target_type="intel_run",
        target_id="test-run",
    )
    db_session.flush()
    event.notification.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert client.get("/api/v1/notifications").json()["total"] == 0
    history = client.get("/api/v1/notifications/history").json()
    assert history["total"] == 1
    assert history["items"][0]["event_key"] == "intel.collection:test-run"


def test_mark_all_notifications_read(client, db_session) -> None:
    for index in range(3):
        create_system_event(
            db_session,
            event_key=f"asset.created:{index}",
            category="asset",
            event_type="asset_created",
            level="success",
            title="新增资产",
            summary=f"新增资产 {index}",
        )
    db_session.commit()

    assert client.post("/api/v1/notifications/read-all").json() == {
        "updated_count": 3
    }
    assert client.get("/api/v1/notifications/unread-count").json() == {"count": 0}


def test_email_settings_encrypt_password_and_never_return_it(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("VULNFLANKER_SECRET_ENCRYPTION_KEY", "test-secret-key")
    get_settings.cache_clear()
    try:
        response = client.patch(
            "/api/v1/email-settings",
            json={
                "enabled": True,
                "automatic_enabled": True,
                "risk_threshold": "high",
                "retry_enabled": True,
                "smtp_host": "smtp.example.test",
                "smtp_port": 587,
                "smtp_security": "starttls",
                "smtp_username": "alerts@example.test",
                "smtp_password": "smtp-password-value",
                "sender_name": "VulnFlanker",
                "sender_email": "alerts@example.test",
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["has_password"] is True
        assert "smtp_password" not in payload
        assert "ciphertext" not in response.text

        stored = db_session.get(EmailSettings, "default")
        assert stored is not None
        assert stored.smtp_password_ciphertext.startswith("fernet:v1:")
        assert "smtp-password-value" not in stored.smtp_password_ciphertext
        audit = db_session.scalar(
            select(AuditLog).where(AuditLog.action == "email_settings.updated")
        )
        assert audit is not None
        assert "smtp-password-value" not in str(audit.details_json)
    finally:
        get_settings.cache_clear()


def test_email_password_requires_encryption_key() -> None:
    settings = Settings(
        _env_file=None,
        secret_encryption_key=None,
        ai_key_encryption_key=None,
    )
    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        encrypt_secret("must-not-be-plain-text", settings=settings)


def test_template_preview_rejects_unknown_tokens_and_unsafe_html() -> None:
    with pytest.raises(ValueError, match="Unsupported template variables"):
        preview_email_templates(
            subject_template="{{unknown}}",
            text_body_template="{{risk_list_text}}",
            html_body_template="{{risk_list_html}}",
        )
    with pytest.raises(ValueError, match="unsafe HTML"):
        preview_email_templates(
            subject_template="{{platform_name}}",
            text_body_template="{{risk_list_text}}",
            html_body_template="<script>alert(1)</script>{{risk_list_html}}",
        )

    preview = preview_email_templates(
        subject_template="{{platform_name}} / {{risk_count}}",
        text_body_template="{{recipient_name}}\n{{risk_list_text}}",
        html_body_template="<p>{{recipient_name}}</p>{{risk_list_html}}",
    )
    assert preview.subject == "VulnFlanker / 2"
    assert "RISK-20260805-0001" in preview.text_body
    assert "<table>" in preview.html_body


def test_delivery_retries_three_times_then_fails(db_session, monkeypatch) -> None:
    settings = email_alerts.get_email_settings(db_session)
    settings.enabled = True
    settings.smtp_host = "smtp.example.test"
    settings.sender_email = "alerts@example.test"
    db_session.add(settings)
    delivery = create_email_delivery(
        db_session,
        trigger_type="manual",
        recipient_email="owner@example.test",
        recipient_name="Owner",
        subject="Test",
        text_body="Test",
        html_body="<p>Test</p>",
        retry_enabled=True,
    )
    db_session.commit()

    def fail_send(*_args, **_kwargs):
        raise OSError("temporary smtp failure")

    monkeypatch.setattr(email_alerts, "_smtp_send", fail_send)
    expected_statuses = [
        "retry_scheduled",
        "retry_scheduled",
        "retry_scheduled",
        "failed",
    ]
    for attempt_index, expected in enumerate(expected_statuses):
        delivery = send_email_delivery(db_session, delivery.id)
        assert delivery is not None
        assert delivery.status == expected
        if delivery.next_attempt_at is not None:
            assert delivery.last_attempt_at is not None
            assert int(
                (delivery.next_attempt_at - delivery.last_attempt_at).total_seconds()
            ) == email_alerts.RETRY_DELAYS_SECONDS[attempt_index]
            delivery.next_attempt_at = utcnow() - timedelta(seconds=1)
            db_session.add(delivery)
            db_session.commit()

    assert delivery.attempt_count == 4
    assert [attempt.status for attempt in delivery.attempts] == ["failed"] * 4
    assert delivery.next_attempt_at is None


def test_delivery_success_records_attempt(db_session, monkeypatch) -> None:
    settings = email_alerts.get_email_settings(db_session)
    settings.enabled = True
    settings.smtp_host = "smtp.example.test"
    settings.sender_email = "alerts@example.test"
    db_session.add(settings)
    delivery = create_email_delivery(
        db_session,
        trigger_type="test",
        recipient_email="owner@example.test",
        recipient_name="Owner",
        subject="Test",
        text_body="Test",
        html_body="<p>Test</p>",
    )
    db_session.commit()
    monkeypatch.setattr(email_alerts, "_smtp_send", lambda *_args, **_kwargs: None)

    result = send_email_delivery(db_session, delivery.id)
    assert result is not None
    assert result.status == "sent"
    assert result.attempt_count == 1
    assert result.sent_at is not None
    assert len(result.attempts) == 1
    assert result.attempts[0].status == "sent"
