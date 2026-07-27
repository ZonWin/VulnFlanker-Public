from __future__ import annotations

from sqlalchemy import select

from app.ai.base import AIMessage
from app.core.config import get_settings
from app.db.models import (
    AICallLog,
    AIProfile,
    AuditLog,
    Vulnerability,
    VulnerabilityAIEnrichment,
)
from app.services.ai_completion import complete_json, decode_api_key


def _profile_payload(**overrides):
    payload = {
        "profile_key": "basic_extraction_profile",
        "display_name": "Basic extraction",
        "provider": "fake",
        "model": "fake-json-model",
        "enabled": True,
        "supports_web_search": False,
        "allow_external_network": False,
        "json_mode": True,
        "timeout_seconds": 10,
        "temperature": 0.0,
    }
    payload.update(overrides)
    return payload


def test_ai_profile_can_be_created_without_returning_api_key(
    client,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("VULNFLANKER_AI_KEY_ENCRYPTION_KEY", "test-encryption-key")
    get_settings.cache_clear()

    response = client.post(
        "/api/v1/ai/profiles",
        json=_profile_payload(api_key="secret-value"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_key"] == "basic_extraction_profile"
    assert payload["provider"] == "fake"
    assert payload["model_vendor"] == "openai"
    assert payload["has_api_key"] is True
    assert "api_key" not in payload
    assert "api_key_ciphertext" not in payload

    profile = db_session.scalar(select(AIProfile))
    assert profile is not None
    assert profile.api_key_ciphertext.startswith("fernet:")
    assert profile.api_key_ciphertext != "secret-value"
    assert "secret-value" not in profile.api_key_ciphertext
    assert decode_api_key(profile.api_key_ciphertext) == "secret-value"

    audit_log = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "ai_profile.created")
    )
    assert audit_log is not None
    assert audit_log.details_json["has_api_key"] is True
    get_settings.cache_clear()


def test_ai_profile_api_key_requires_encryption_key(client) -> None:
    get_settings.cache_clear()

    response = client.post(
        "/api/v1/ai/profiles",
        json=_profile_payload(api_key="secret-value"),
    )

    assert response.status_code == 400
    assert "VULNFLANKER_AI_KEY_ENCRYPTION_KEY" in response.json()["detail"]


def test_ai_api_key_decoder_keeps_legacy_formats() -> None:
    assert decode_api_key("b64:c2VjcmV0LXZhbHVl") == "secret-value"
    assert decode_api_key("plain:secret-value") == "secret-value"


def test_ai_profile_key_must_be_unique(client) -> None:
    first = client.post("/api/v1/ai/profiles", json=_profile_payload())
    assert first.status_code == 200

    second = client.post("/api/v1/ai/profiles", json=_profile_payload())

    assert second.status_code == 400
    assert "already exists" in second.json()["detail"]


def test_ai_profile_can_be_updated_and_listed(client) -> None:
    create_response = client.post("/api/v1/ai/profiles", json=_profile_payload())
    profile_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/ai/profiles/{profile_id}",
        json={
            "display_name": "Updated profile",
            "model_vendor": "kimi",
            "supports_web_search": True,
            "allow_external_network": True,
            "daily_call_limit": 25,
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["display_name"] == "Updated profile"
    assert updated["model_vendor"] == "kimi"
    assert updated["supports_web_search"] is True
    assert updated["allow_external_network"] is True
    assert updated["daily_call_limit"] == 25
    assert updated["prompt_template"]["template_key"] == "vuln_enrichment.extract_from_existing_v1"
    assert "output contract" in updated["prompt_template"]["user_prompt_template"]

    list_response = client.get("/api/v1/ai/profiles")
    assert list_response.status_code == 200
    assert list_response.json()[0]["display_name"] == "Updated profile"
    assert list_response.json()[0]["prompt_template"]["system_prompt"]


def test_ai_profile_prompt_template_can_be_customized(client, db_session) -> None:
    create_response = client.post("/api/v1/ai/profiles", json=_profile_payload())
    profile_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/ai/profiles/{profile_id}",
        json={
            "prompt_template": {
                "system_prompt": "Custom system prompt.",
                "user_prompt_template": "Use {output_contract} and {enrichment_input_json}.",
                "output_contract": "Custom output contract.",
            }
        },
    )

    assert update_response.status_code == 200
    prompt_template = update_response.json()["prompt_template"]
    assert prompt_template["customized"] is True
    assert prompt_template["system_prompt"] == "Custom system prompt."
    assert prompt_template["user_prompt_template"].startswith("Use {output_contract}")
    assert prompt_template["output_contract"] == "Custom output contract."

    profile = db_session.get(AIProfile, profile_id)
    assert profile.custom_system_prompt == "Custom system prompt."
    assert (
        profile.custom_user_prompt_template
        == "Use {output_contract} and {enrichment_input_json}."
    )
    assert profile.custom_output_contract == "Custom output contract."


def test_ai_profile_key_can_be_updated(client) -> None:
    create_response = client.post(
        "/api/v1/ai/profiles",
        json=_profile_payload(profile_key="DeepSeek"),
    )
    profile_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/ai/profiles/{profile_id}",
        json={"profile_key": "basic_extraction_profile"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["profile_key"] == "basic_extraction_profile"


def test_ai_profile_key_update_must_be_unique(client) -> None:
    first = client.post(
        "/api/v1/ai/profiles",
        json=_profile_payload(profile_key="basic_extraction_profile"),
    )
    second = client.post(
        "/api/v1/ai/profiles",
        json=_profile_payload(profile_key="DeepSeek"),
    )
    assert first.status_code == 200
    assert second.status_code == 200

    response = client.patch(
        f"/api/v1/ai/profiles/{second.json()['id']}",
        json={"profile_key": "basic_extraction_profile"},
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_ai_profile_can_be_deleted_without_losing_history(client, db_session) -> None:
    create_response = client.post("/api/v1/ai/profiles", json=_profile_payload())
    profile_id = create_response.json()["id"]
    vulnerability = Vulnerability(
        canonical_id="CVE-2026-AI-PROFILE-DELETE",
        title="Profile delete history",
    )
    db_session.add(vulnerability)
    db_session.flush()
    call_log = AICallLog(
        profile_id=profile_id,
        task_type="vulnerability_enrichment_layer1",
        target_type="vulnerability",
        target_id=vulnerability.id,
        request_hash="delete-profile-request",
        model="fake-json-model",
        status="success",
    )
    enrichment = VulnerabilityAIEnrichment(
        vulnerability_id=vulnerability.id,
        layer="existing_data_extraction",
        source_mode="existing_raw",
        profile_id=profile_id,
        model="fake-json-model",
        input_hash="delete-profile-input",
        status="insufficient",
        evidence_json=[],
        source_urls_json=[],
        conflicts_json=[],
        raw_output_json={},
    )
    db_session.add_all([call_log, enrichment])
    db_session.commit()

    response = client.delete(f"/api/v1/ai/profiles/{profile_id}")

    assert response.status_code == 200
    assert response.json()["id"] == profile_id
    assert db_session.get(AIProfile, profile_id) is None
    db_session.refresh(call_log)
    db_session.refresh(enrichment)
    assert call_log.profile_id is None
    assert enrichment.profile_id is None

    audit_log = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "ai_profile.deleted")
    )
    assert audit_log is not None
    assert audit_log.details_json["profile_key"] == "basic_extraction_profile"


def test_ai_profile_rejects_unsupported_provider(client) -> None:
    response = client.post(
        "/api/v1/ai/profiles",
        json=_profile_payload(provider="unknown-provider"),
    )

    assert response.status_code == 400
    assert "Unsupported AI provider" in response.json()["detail"]


def test_ai_profile_rejects_unsupported_model_vendor(client) -> None:
    response = client.post(
        "/api/v1/ai/profiles",
        json=_profile_payload(model_vendor="unknown-vendor"),
    )

    assert response.status_code == 400
    assert "Unsupported AI model vendor" in response.json()["detail"]


def test_ai_profile_test_uses_fake_provider_and_writes_call_log(client, db_session) -> None:
    create_response = client.post("/api/v1/ai/profiles", json=_profile_payload())
    profile_id = create_response.json()["id"]

    response = client.post(f"/api/v1/ai/profiles/{profile_id}/test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "success"
    assert payload["model"] == "fake-json-model"

    call_log = db_session.scalar(select(AICallLog))
    assert call_log is not None
    assert call_log.profile_id == profile_id
    assert call_log.task_type == "ai_profile_test"
    assert call_log.status == "success"
    assert call_log.total_tokens == 2

    audit_log = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "ai_profile.tested")
    )
    assert audit_log is not None
    assert audit_log.outcome == "success"


def test_fake_provider_failure_is_logged(db_session) -> None:
    profile = AIProfile(
        profile_key="test_failure_profile",
        display_name="Test failure",
        provider="fake",
        model="fake-json-model",
        enabled=True,
        supports_web_search=False,
        allow_external_network=False,
        json_mode=True,
        timeout_seconds=10,
        temperature=0.0,
    )
    db_session.add(profile)
    db_session.commit()

    result = complete_json(
        db_session,
        profile,
        messages=[AIMessage(role="user", content="test")],
        task_type="unit_test",
        target_type="ai_profile",
        target_id=profile.id,
        metadata={"force_error": True},
    )
    db_session.commit()

    assert result.status == "failed"
    call_log = db_session.scalar(select(AICallLog))
    assert call_log is not None
    assert call_log.status == "failed"
    assert call_log.error_message == "Fake provider forced failure."


def test_ai_completion_respects_profile_daily_call_limit(db_session) -> None:
    profile = AIProfile(
        profile_key="limited_profile",
        display_name="Limited profile",
        provider="fake",
        model="fake-json-model",
        enabled=True,
        supports_web_search=False,
        allow_external_network=False,
        json_mode=True,
        timeout_seconds=10,
        temperature=0.0,
        daily_call_limit=1,
    )
    db_session.add(profile)
    db_session.commit()

    first = complete_json(
        db_session,
        profile,
        messages=[AIMessage(role="user", content="test")],
        task_type="unit_test",
        target_type="ai_profile",
        target_id=profile.id,
    )
    second = complete_json(
        db_session,
        profile,
        messages=[AIMessage(role="user", content="test again")],
        task_type="unit_test",
        target_type="ai_profile",
        target_id=profile.id,
    )
    db_session.commit()

    assert first.status == "success"
    assert second.status == "failed"
    assert "daily call limit" in (second.error_message or "")

    logs = db_session.scalars(select(AICallLog).order_by(AICallLog.created_at)).all()
    assert [log.status for log in logs] == ["success", "failed"]
    assert logs[1].profile_id == profile.id
