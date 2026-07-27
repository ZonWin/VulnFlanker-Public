from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user
from app.db.models import Asset, AuditLog, BusinessSystem, User
from app.main import app
from app.services.auth import hash_password


def _create_team(client: TestClient, *, code: str = " pay-sre ", name: str = "支付 SRE") -> dict:
    response = client.post(
        "/api/v1/responsibility-teams",
        json={"code": code, "name": name, "description": "支付业务保障团队"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_person(
    client: TestClient,
    team_id: str,
    *,
    employee_no: str = "E1001",
    name: str = "张三",
) -> dict:
    response = client.post(
        "/api/v1/people",
        json={
            "employee_no": employee_no,
            "name": name,
            "email": f"{employee_no.lower()}@example.com",
            "team_id": team_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_system(
    client: TestClient,
    person_id: str,
    *,
    code: str = " payment ",
    name: str = "支付系统",
) -> dict:
    response = client.post(
        "/api/v1/business-systems",
        json={
            "code": code,
            "name": name,
            "responsible_person_id": person_id,
            "status": "active",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_master_data_crud_counts_filters_and_audit(client, db_session: Session) -> None:
    team = _create_team(client)
    assert team["code"] == "PAY-SRE"
    assert team["version"] == 1

    person = _create_person(client, team["id"])
    assert person["email"] == "e1001@example.com"
    assert person["team"]["id"] == team["id"]

    system = _create_system(client, person["id"])
    assert system["code"] == "PAYMENT"
    assert system["responsible_person"]["id"] == person["id"]

    asset = Asset(
        hostname="pay-web-01",
        business_system_id=system["id"],
        ownership_source="manual",
    )
    db_session.add(asset)
    db_session.commit()

    teams = client.get(
        "/api/v1/responsibility-teams",
        params={"keyword": "PAY", "has_members": "true"},
    )
    assert teams.status_code == 200
    assert teams.json()["total"] == 1
    assert teams.json()["items"][0]["person_count"] == 1
    assert teams.json()["items"][0]["business_system_count"] == 1
    assert teams.json()["items"][0]["asset_count"] == 1

    people = client.get(
        "/api/v1/people",
        params={"team_id": team["id"], "has_email": "true", "has_systems": "true"},
    )
    assert people.status_code == 200
    assert people.json()["items"][0]["business_system_count"] == 1
    assert people.json()["items"][0]["asset_count"] == 1

    systems = client.get(
        "/api/v1/business-systems",
        params={"team_id": team["id"], "has_assets": "true"},
    )
    assert systems.status_code == 200
    assert systems.json()["items"][0]["asset_count"] == 1

    summary = client.get("/api/v1/ownership/summary")
    assert summary.status_code == 200
    assert summary.json() == {
        "team_count": 1,
        "person_count": 1,
        "business_system_count": 1,
        "asset_count": 1,
        "complete_asset_count": 1,
        "unassigned_asset_count": 0,
        "incomplete_asset_count": 0,
    }

    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert {
        "ownership.team.created",
        "ownership.person.created",
        "ownership.system.created",
    }.issubset(actions)


def test_unique_and_stale_version_errors_have_machine_codes(client) -> None:
    team = _create_team(client)

    duplicate = client.post(
        "/api/v1/responsibility-teams",
        json={"code": "OTHER", "name": "支付SRE"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_code"

    updated = client.patch(
        f"/api/v1/responsibility-teams/{team['id']}",
        json={"expected_version": 1, "name": "支付保障团队"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = client.patch(
        f"/api/v1/responsibility-teams/{team['id']}",
        json={"expected_version": 1, "name": "过期修改"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_version"
    assert stale.json()["detail"]["details"]["current_version"] == 2


def test_relationship_validation_and_dependency_protection(client, db_session: Session) -> None:
    team = _create_team(client)
    person = _create_person(client, team["id"])
    system = _create_system(client, person["id"])
    db_session.add(Asset(hostname="pay-api-01", business_system_id=system["id"]))
    db_session.commit()

    team_conflict = client.post(
        f"/api/v1/responsibility-teams/{team['id']}/deactivate",
        json={"expected_version": team["version"]},
    )
    assert team_conflict.status_code == 409
    assert team_conflict.json()["detail"]["code"] == "dependency_conflict"
    assert team_conflict.json()["detail"]["details"]["active_person_count"] == 1

    person_conflict = client.post(
        f"/api/v1/people/{person['id']}/deactivate",
        json={"expected_version": person["version"]},
    )
    assert person_conflict.status_code == 409
    assert person_conflict.json()["detail"]["details"]["business_system_count"] == 1

    system_conflict = client.post(
        f"/api/v1/business-systems/{system['id']}/deactivate",
        json={"expected_version": system["version"]},
    )
    assert system_conflict.status_code == 409
    assert system_conflict.json()["detail"]["details"]["asset_count"] == 1


def test_deactivation_can_atomically_reassign_systems_and_assets(
    client,
    db_session: Session,
) -> None:
    team = _create_team(client)
    original_person = _create_person(client, team["id"])
    replacement_person = _create_person(
        client,
        team["id"],
        employee_no="E1002",
        name="李四",
    )
    original_system = _create_system(client, original_person["id"])
    replacement_system = _create_system(
        client,
        replacement_person["id"],
        code="ORDER",
        name="订单系统",
    )
    asset = Asset(hostname="pay-worker-01", business_system_id=original_system["id"])
    db_session.add(asset)
    db_session.commit()

    person_response = client.post(
        f"/api/v1/people/{original_person['id']}/deactivate",
        json={
            "expected_version": original_person["version"],
            "replacement_person_id": replacement_person["id"],
        },
    )
    assert person_response.status_code == 200
    assert person_response.json()["status"] == "inactive"
    reassigned_system = db_session.get(BusinessSystem, original_system["id"])
    assert reassigned_system is not None
    assert reassigned_system.responsible_person_id == replacement_person["id"]

    system_response = client.post(
        f"/api/v1/business-systems/{original_system['id']}/deactivate",
        json={
            "expected_version": reassigned_system.version,
            "replacement_system_id": replacement_system["id"],
        },
    )
    assert system_response.status_code == 200
    db_session.refresh(asset)
    assert asset.business_system_id == replacement_system["id"]
    assert asset.ownership_source == "manual"
    assert asset.ownership_updated_at is not None


def test_transfer_members_updates_downstream_team_projection(client) -> None:
    original_team = _create_team(client)
    target_team = _create_team(client, code="SECOPS", name="安全运营")
    person = _create_person(client, original_team["id"])
    system = _create_system(client, person["id"])

    response = client.post(
        f"/api/v1/responsibility-teams/{target_team['id']}/transfer-members",
        json={"person_ids": [person["id"]]},
    )
    assert response.status_code == 200
    assert response.json()["person_count"] == 1

    refreshed = client.get(f"/api/v1/business-systems/{system['id']}")
    assert refreshed.status_code == 200
    assert refreshed.json()["responsible_person"]["team"]["id"] == target_team["id"]


def test_system_owner_change_updates_asset_projection_and_audit(
    client,
    db_session: Session,
) -> None:
    original_team = _create_team(client)
    replacement_team = _create_team(client, code="APP-OPS", name="应用运维")
    original_person = _create_person(client, original_team["id"])
    replacement_person = _create_person(
        client,
        replacement_team["id"],
        employee_no="E2002",
        name="王五",
    )
    system = _create_system(client, original_person["id"])
    asset = Asset(hostname="owner-change-asset", business_system_id=system["id"])
    db_session.add(asset)
    db_session.commit()

    response = client.patch(
        f"/api/v1/business-systems/{system['id']}",
        json={
            "expected_version": system["version"],
            "responsible_person_id": replacement_person["id"],
        },
    )
    assert response.status_code == 200

    projected = client.get(f"/api/v1/assets/{asset.id}").json()["ownership"]
    assert projected["responsible_person"]["id"] == replacement_person["id"]
    assert projected["responsibility_team"]["id"] == replacement_team["id"]
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "ownership.system.owner_changed")
    )
    assert audit is not None
    assert audit.actor_id == "test-admin-user"
    assert audit.details_json["before"]["responsible_person_id"] == original_person["id"]
    assert audit.details_json["after"]["responsible_person_id"] == replacement_person["id"]
    assert audit.details_json["affected_asset_count"] == 1


def test_inactive_relationships_cannot_be_activated_or_assigned(client) -> None:
    team = _create_team(client)
    deactivated = client.post(
        f"/api/v1/responsibility-teams/{team['id']}/deactivate",
        json={"expected_version": team["version"]},
    )
    assert deactivated.status_code == 200

    person_response = client.post(
        "/api/v1/people",
        json={"name": "不可启用人员", "team_id": team["id"], "status": "active"},
    )
    assert person_response.status_code == 400
    assert person_response.json()["detail"]["code"] == "invalid_relationship"


def test_ownership_reads_require_login(anonymous_client) -> None:
    assert anonymous_client.get("/api/v1/responsibility-teams").status_code == 401
    assert anonymous_client.get("/api/v1/people").status_code == 401
    assert anonymous_client.get("/api/v1/business-systems").status_code == 401


def test_ownership_writes_require_superuser(db_session: Session) -> None:
    viewer = User(
        username="ownership-viewer",
        display_name="Ownership Viewer",
        password_hash=hash_password("viewer-password"),
        is_superuser=False,
        is_active=True,
    )
    db_session.add(viewer)
    db_session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_current_user() -> User:
        return viewer

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_current_user] = override_current_user
    try:
        with TestClient(app) as viewer_client:
            assert viewer_client.get("/api/v1/responsibility-teams").status_code == 200
            response = viewer_client.post(
                "/api/v1/responsibility-teams",
                json={"code": "VIEWER", "name": "只读用户团队"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
