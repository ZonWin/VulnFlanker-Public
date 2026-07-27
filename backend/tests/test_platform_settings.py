from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user
from app.app_factory import create_console_app
from app.db.models import AuditLog, PlatformSettings
from app.db.models.user import User


TINY_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def test_platform_settings_are_public_for_login_page(anonymous_client) -> None:
    response = anonymous_client.get("/api/v1/platform-settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["platform_name"] == "VulnFlanker"
    assert payload["platform_subtitle"] == "漏洞监测平台"
    assert payload["logo_data_url"] is None
    assert payload["ai_enabled"] is True
    assert payload["ai_auto_enrich_enabled"] is False
    assert payload["ai_auto_accept_policy"] == "moderate"
    assert payload["ai_web_auto_accept_confidence"] == 0.8


def test_platform_settings_route_is_registered_in_console_app(
    db_session: Session,
    authenticated_user: User,
) -> None:
    console_app = create_console_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_require_current_user() -> User:
        return authenticated_user

    console_app.dependency_overrides[get_db] = override_get_db
    console_app.dependency_overrides[require_current_user] = override_require_current_user
    try:
        response = TestClient(console_app).get("/api/v1/platform-settings")
    finally:
        console_app.dependency_overrides.clear()

    assert response.status_code == 200


def test_platform_settings_can_be_updated(client, db_session) -> None:
    response = client.patch(
        "/api/v1/platform-settings",
        json={
            "platform_name": "Acme SecOps",
            "platform_subtitle": "风险治理平台",
            "logo_data_url": TINY_PNG_DATA_URL,
            "ai_auto_enrich_enabled": True,
            "ai_auto_accept_enabled": True,
            "ai_auto_accept_policy": "strict",
            "ai_auto_accept_confidence": 0.92,
            "ai_web_auto_accept_confidence": 0.81,
            "ai_layer2_daily_limit": 8,
            "ai_batch_max_size": 42,
            "ai_allow_web_enrichment_default": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["platform_name"] == "Acme SecOps"
    assert payload["platform_subtitle"] == "风险治理平台"
    assert payload["logo_data_url"] == TINY_PNG_DATA_URL
    assert payload["ai_auto_enrich_enabled"] is True
    assert payload["ai_auto_accept_enabled"] is True
    assert payload["ai_auto_accept_policy"] == "strict"
    assert payload["ai_auto_accept_confidence"] == 0.92
    assert payload["ai_web_auto_accept_confidence"] == 0.81
    assert payload["ai_layer2_daily_limit"] == 8
    assert payload["ai_batch_max_size"] == 42
    assert payload["ai_allow_web_enrichment_default"] is True

    settings = db_session.get(PlatformSettings, "default")
    assert settings is not None
    assert settings.platform_name == "Acme SecOps"
    assert settings.ai_batch_max_size == 42

    audit_log = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "platform_settings.updated")
    )
    assert audit_log is not None
    assert audit_log.details_json["has_custom_logo"] is True
    assert audit_log.details_json["ai_auto_enrich_enabled"] is True


def test_platform_settings_accepts_three_auto_accept_policies(client) -> None:
    for policy in ("strict", "moderate", "relaxed"):
        response = client.patch(
            "/api/v1/platform-settings",
            json={"ai_auto_accept_policy": policy},
        )
        assert response.status_code == 200
        assert response.json()["ai_auto_accept_policy"] == policy


def test_platform_settings_patch_requires_authentication(anonymous_client) -> None:
    response = anonymous_client.patch(
        "/api/v1/platform-settings",
        json={"platform_name": "Nope"},
    )

    assert response.status_code == 401


def test_platform_settings_reject_invalid_logo(client) -> None:
    response = client.patch(
        "/api/v1/platform-settings",
        json={"logo_data_url": "data:text/plain;base64,SGVsbG8="},
    )

    assert response.status_code == 400
    assert "logo_data_url" in response.json()["detail"]


def test_platform_settings_reset_restores_defaults(client) -> None:
    client.patch(
        "/api/v1/platform-settings",
        json={
            "platform_name": "Acme SecOps",
            "platform_subtitle": "风险治理平台",
            "logo_data_url": TINY_PNG_DATA_URL,
        },
    )

    response = client.post("/api/v1/platform-settings/reset")

    assert response.status_code == 200
    payload = response.json()
    assert payload["platform_name"] == "VulnFlanker"
    assert payload["platform_subtitle"] == "漏洞监测平台"
    assert payload["logo_data_url"] is None
