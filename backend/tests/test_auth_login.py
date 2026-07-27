from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.models import User, UserSession
from app.services.auth import ensure_bootstrap_admin, hash_password, hash_session_token


def _create_user(
    db_session: Session,
    *,
    username: str = "admin",
    password: str = "correct-password",
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        display_name="Admin",
        password_hash=hash_password(password),
        is_superuser=True,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def no_bootstrap_admin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VULNFLANKER_BOOTSTRAP_ADMIN_PASSWORD", "")
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


def test_login_sets_session_cookie_and_me_returns_user(
    anonymous_client,
    db_session: Session,
) -> None:
    user = _create_user(db_session)

    response = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id
    assert "vulnflanker_session" in response.cookies

    me_response = anonymous_client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"


def test_login_rejects_invalid_password(
    anonymous_client,
    db_session: Session,
) -> None:
    _create_user(db_session)

    response = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_logout_revokes_session(
    anonymous_client,
    db_session: Session,
) -> None:
    _create_user(db_session)
    login_response = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-password"},
    )
    assert login_response.status_code == 200

    logout_response = anonymous_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204
    set_cookie = logout_response.headers["set-cookie"]
    assert "vulnflanker_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie

    me_response = anonymous_client.get("/api/v1/auth/me")
    assert me_response.status_code == 401


def test_expired_session_is_rejected(
    anonymous_client,
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    token = "expired-token"
    db_session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=utcnow() - timedelta(seconds=1),
        )
    )
    db_session.commit()
    anonymous_client.cookies.set("vulnflanker_session", token)

    response = anonymous_client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_bootstrap_admin_uses_environment_settings(db_session: Session) -> None:
    class SettingsStub:
        bootstrap_admin_username = "bootstrap-admin"
        bootstrap_admin_password = "bootstrap-password"
        bootstrap_admin_display_name = "Bootstrap Admin"

    user = ensure_bootstrap_admin(db_session, settings=SettingsStub())  # type: ignore[arg-type]

    assert user is not None
    assert user.username == "bootstrap-admin"
    assert user.is_superuser is True
    assert user.is_active is True


def test_setup_status_reports_needs_setup_without_admin(
    anonymous_client,
    no_bootstrap_admin,
) -> None:
    response = anonymous_client.get("/api/v1/auth/setup-status")

    assert response.status_code == 200
    assert response.json() == {
        "needs_setup": True,
        "has_active_superuser": False,
    }


def test_setup_admin_creates_admin_and_sets_session_cookie(
    anonymous_client,
    db_session: Session,
    no_bootstrap_admin,
) -> None:
    response = anonymous_client.post(
        "/api/v1/auth/setup-admin",
        json={
            "username": "initial-admin",
            "password": "strong-password",
            "display_name": "Initial Admin",
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["username"] == "initial-admin"
    assert response.json()["user"]["is_superuser"] is True
    assert "vulnflanker_session" in response.cookies

    user = db_session.query(User).filter(User.username == "initial-admin").one()
    assert user.display_name == "Initial Admin"
    assert user.is_active is True


def test_setup_admin_rejects_duplicate_initialization(
    anonymous_client,
    no_bootstrap_admin,
) -> None:
    first_response = anonymous_client.post(
        "/api/v1/auth/setup-admin",
        json={"username": "admin", "password": "strong-password"},
    )
    assert first_response.status_code == 201

    second_response = anonymous_client.post(
        "/api/v1/auth/setup-admin",
        json={"username": "another-admin", "password": "another-password"},
    )

    assert second_response.status_code == 409
