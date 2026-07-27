from __future__ import annotations


def test_console_route_requires_login(anonymous_client) -> None:
    response = anonymous_client.get("/api/v1/assets")

    assert response.status_code == 401


def test_agent_legacy_heartbeat_does_not_require_web_login(anonymous_client) -> None:
    response = anonymous_client.post(
        "/api/v1/agents/heartbeat",
        json={
            "agent_id": "agent-auth-boundary",
            "hostname": "auth-boundary-host",
            "platform": "linux",
            "version": "0.1.0",
        },
    )

    assert response.status_code == 202


def test_webhook_keeps_its_own_token_boundary(anonymous_client) -> None:
    response = anonymous_client.post(
        "/api/v1/intel/watchvuln/webhook",
        headers={"X-VulnFlanker-Token": "change-me"},
        json={},
    )

    assert response.json().get("detail") != "Authentication required"
