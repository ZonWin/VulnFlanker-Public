from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user
from app.app_factory import create_agent_app, create_console_app, create_legacy_app
from app.core.config import get_settings
from app.db.base import utcnow
from app.db.models import AgentCredential, AgentEnrollmentToken, AgentStatus, User
from app.services.agent_auth import hash_agent_secret, public_enrollment_token_preview
from app.services.auth import hash_password
from test_asset_ingestion import build_linux_snapshot


def _override_db(db_session: Session):
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    return override_get_db


def _override_user(authenticated_user: User):
    def override_require_current_user() -> User:
        return authenticated_user

    return override_require_current_user


def test_agent_ingress_exposes_only_agent_prefix(db_session) -> None:
    db_session.add(
        AgentEnrollmentToken(
            name="test-token",
            token_hash=hash_agent_secret("enroll-test-token"),
            max_uses=1,
            used_count=0,
        )
    )
    db_session.commit()
    app = create_agent_app()
    app.dependency_overrides[get_db] = _override_db(db_session)

    try:
        with TestClient(app) as client:
            assets_response = client.get("/api/v1/assets")
            enroll_response = client.post(
                "/agent/v1/enroll",
                json={
                    "enrollment_token": "enroll-test-token",
                    "agent_id": "agent-ingress-isolation",
                    "hostname": "ingress-host",
                    "platform": "linux",
                    "version": "0.1.0",
                },
            )
            agent_secret = enroll_response.json()["agent_secret"]
            heartbeat_response = client.post(
                "/agent/v1/heartbeat",
                headers={"Authorization": f"Bearer {agent_secret}"},
                json={
                    "agent_id": "agent-ingress-isolation",
                    "hostname": "ingress-host",
                    "platform": "linux",
                    "version": "0.1.0",
                },
            )
            poll_response = client.get(
                "/agent/v1/tasks/next",
                headers={"Authorization": f"Bearer {agent_secret}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert assets_response.status_code == 404
    assert enroll_response.status_code == 201
    assert heartbeat_response.status_code == 202
    assert poll_response.status_code == 200


def test_agent_ingress_requires_valid_bearer_secret(db_session) -> None:
    app = create_agent_app()
    app.dependency_overrides[get_db] = _override_db(db_session)

    try:
        with TestClient(app) as client:
            missing_response = client.post(
                "/agent/v1/heartbeat",
                json={
                    "agent_id": "agent-auth-required",
                    "hostname": "auth-required-host",
                    "platform": "linux",
                    "version": "0.1.0",
                },
            )
            invalid_response = client.post(
                "/agent/v1/heartbeat",
                headers={"Authorization": "Bearer bad-secret"},
                json={
                    "agent_id": "agent-auth-required",
                    "hostname": "auth-required-host",
                    "platform": "linux",
                    "version": "0.1.0",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert missing_response.status_code == 401
    assert invalid_response.status_code == 401


def test_console_app_does_not_expose_agent_ingress(
    db_session,
    authenticated_user,
) -> None:
    app = create_console_app()
    app.dependency_overrides[get_db] = _override_db(db_session)
    app.dependency_overrides[require_current_user] = _override_user(authenticated_user)

    try:
        with TestClient(app) as client:
            ingress_response = client.post(
                "/agent/v1/heartbeat",
                json={
                    "agent_id": "console-boundary",
                    "hostname": "console-boundary-host",
                    "platform": "linux",
                    "version": "0.1.0",
                },
            )
            legacy_heartbeat_response = client.post(
                "/api/v1/agents/heartbeat",
                json={
                    "agent_id": "console-legacy-boundary",
                    "hostname": "console-legacy-boundary-host",
                    "platform": "linux",
                    "version": "0.1.0",
                },
            )
            agents_response = client.get("/api/v1/agents")
    finally:
        app.dependency_overrides.clear()

    assert ingress_response.status_code == 404
    assert legacy_heartbeat_response.status_code in {404, 405}
    assert agents_response.status_code == 200


def test_console_app_manages_agent_enrollment_tokens(
    db_session,
    authenticated_user,
) -> None:
    app = create_console_app()
    app.dependency_overrides[get_db] = _override_db(db_session)
    app.dependency_overrides[require_current_user] = _override_user(authenticated_user)

    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/agents/enrollment-tokens",
                json={
                    "name": "phase3-token",
                    "expires_at": (utcnow() + timedelta(days=7)).isoformat(),
                    "max_uses": 2,
                },
            )
            created = create_response.json()
            list_response = client.get("/api/v1/agents/enrollment-tokens")
            revoke_response = client.post(
                f"/api/v1/agents/enrollment-tokens/{created['id']}/revoke"
            )
            list_after_revoke_response = client.get("/api/v1/agents/enrollment-tokens")
    finally:
        app.dependency_overrides.clear()

    assert create_response.status_code == 201
    assert created["enrollment_token"].startswith("vflet_")
    assert created["token_preview"] == f"vflet_***{created['enrollment_token'][-4:]}"
    assert "..." not in created["token_preview"]
    assert created["token_preview"] != created["enrollment_token"]
    assert created["created_by_display"] == authenticated_user.display_name
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["token_preview"] == created["token_preview"]
    assert listed[0]["created_by_display"] == authenticated_user.display_name
    assert listed[0]["status"] == "active"
    assert "enrollment_token" not in listed[0]
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"
    assert list_after_revoke_response.json()[0]["status"] == "revoked"


def test_disabled_agent_secret_cannot_upload_via_agent_ingress(
    db_session,
    authenticated_user,
) -> None:
    secret = "vfsec-disabled-agent"
    db_session.add(
        AgentCredential(
            agent_id="agent-linux-001",
            secret_hash=hash_agent_secret(secret),
            status="active",
        )
    )
    db_session.add(
        AgentStatus(
            agent_id="agent-linux-001",
            hostname="web-01.prod.local",
            platform="linux",
            version="0.1.0",
            status="online",
            last_heartbeat_at=utcnow(),
        )
    )
    db_session.commit()

    console_app = create_console_app()
    console_app.dependency_overrides[get_db] = _override_db(db_session)
    console_app.dependency_overrides[require_current_user] = _override_user(
        authenticated_user
    )
    try:
        with TestClient(console_app) as client:
            disable_response = client.post("/api/v1/agents/agent-linux-001/disable")
    finally:
        console_app.dependency_overrides.clear()

    agent_app = create_agent_app()
    agent_app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        with TestClient(agent_app) as client:
            snapshot_response = client.post(
                "/agent/v1/snapshots",
                headers={"Authorization": f"Bearer {secret}"},
                json=build_linux_snapshot(),
            )
    finally:
        agent_app.dependency_overrides.clear()

    legacy_app = create_legacy_app()
    legacy_app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        with TestClient(legacy_app) as client:
            legacy_snapshot_response = client.post(
                "/api/v1/agents/snapshots",
                json=build_linux_snapshot(),
            )
    finally:
        legacy_app.dependency_overrides.clear()

    credential = db_session.scalar(
        select(AgentCredential).where(AgentCredential.agent_id == "agent-linux-001")
    )
    status = db_session.scalar(
        select(AgentStatus).where(AgentStatus.agent_id == "agent-linux-001")
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["agent_disabled"] is True
    assert credential is not None
    assert credential.status == "disabled"
    assert credential.revoked_at is not None
    assert status is not None
    assert status.status == "disabled"
    assert snapshot_response.status_code == 401
    assert legacy_snapshot_response.status_code == 403


def test_agent_enrollment_token_preview_masks_legacy_preview() -> None:
    assert (
        public_enrollment_token_preview("vflet_abcd...uvwxyz")
        == "vflet_***wxyz"
    )


def test_console_app_enrollment_token_management_requires_superuser(db_session) -> None:
    user = User(
        id="test-regular-user",
        username="test-regular",
        display_name="Test Regular",
        password_hash=hash_password("test-password"),
        is_superuser=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    app = create_console_app()
    app.dependency_overrides[get_db] = _override_db(db_session)
    app.dependency_overrides[require_current_user] = _override_user(user)

    try:
        with TestClient(app) as client:
            list_response = client.get("/api/v1/agents/enrollment-tokens")
            create_response = client.post(
                "/api/v1/agents/enrollment-tokens",
                json={"name": "regular-user-token", "max_uses": 1},
            )
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 403
    assert create_response.status_code == 403


def test_legacy_app_keeps_old_agent_paths(db_session) -> None:
    app = create_legacy_app()
    app.dependency_overrides[get_db] = _override_db(db_session)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/agents/heartbeat",
                json={
                    "agent_id": "legacy-agent-boundary",
                    "hostname": "legacy-boundary-host",
                    "platform": "linux",
                    "version": "0.1.0",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202


def test_legacy_agent_paths_can_be_disabled(monkeypatch, db_session) -> None:
    monkeypatch.setenv("VULNFLANKER_LEGACY_AGENT_API_ENABLED", "false")
    get_settings.cache_clear()
    app = create_legacy_app()
    app.dependency_overrides[get_db] = _override_db(db_session)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/agents/heartbeat",
                json={
                    "agent_id": "legacy-disabled-boundary",
                    "hostname": "legacy-disabled-host",
                    "platform": "linux",
                    "version": "0.1.0",
                },
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert response.status_code == 404
