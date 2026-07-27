from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user
from app.db.models import (
    Asset,
    AuditLog,
    BusinessSystem,
    Person,
    ResponsibilityTeam,
    User,
)
from app.main import app
from app.services.ownership_migration import migrate_legacy_asset_ownership
from test_asset_ingestion import build_linux_snapshot


def _chain(
    db: Session,
    *,
    suffix: str,
    system_name: str,
    status: str = "active",
) -> tuple[ResponsibilityTeam, Person, BusinessSystem]:
    team = ResponsibilityTeam(
        code=f"TEAM-{suffix}",
        name=f"Team {suffix}",
        normalized_name=f"team{suffix}".casefold(),
        status="active",
    )
    person = Person(name=f"Owner {suffix}", team=team, status="active")
    system = BusinessSystem(
        code=f"SYS-{suffix}",
        name=system_name,
        normalized_name="".join(system_name.split()).casefold(),
        responsible_person=person if status == "active" else None,
        status=status,
    )
    db.add_all([team, person, system])
    db.commit()
    return team, person, system


def test_asset_projection_filters_and_deprecated_text_are_derived(
    client,
    db_session: Session,
) -> None:
    team, person, system = _chain(
        db_session,
        suffix="PAY",
        system_name="支付系统",
    )
    asset = Asset(
        hostname="pay-api-01",
        business_system="wrong legacy system",
        owner_team="wrong legacy team",
        owner_person="wrong legacy person",
        business_system_record=system,
        ownership_source="manual",
    )
    db_session.add(asset)
    db_session.commit()

    detail_response = client.get(f"/api/v1/assets/{asset.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["ownership"]["status"] == "complete"
    assert detail["ownership"]["business_system"]["id"] == system.id
    assert detail["ownership"]["responsible_person"]["id"] == person.id
    assert detail["ownership"]["responsibility_team"]["id"] == team.id
    assert detail["business_system"] == "支付系统"
    assert detail["owner_person"] == "Owner PAY"
    assert detail["owner_team"] == "Team PAY"

    by_system = client.get(f"/api/v1/assets?business_system_id={system.id}").json()
    by_person = client.get(f"/api/v1/assets?responsible_person_id={person.id}").json()
    by_team = client.get(f"/api/v1/assets?responsibility_team_id={team.id}").json()
    complete = client.get("/api/v1/assets?ownership_status=complete").json()
    unassigned = client.get("/api/v1/assets?ownership_status=unassigned").json()
    assert [item["id"] for item in by_system] == [asset.id]
    assert [item["id"] for item in by_person] == [asset.id]
    assert [item["id"] for item in by_team] == [asset.id]
    assert [item["id"] for item in complete] == [asset.id]
    assert unassigned == []


def test_asset_list_ownership_projection_does_not_query_per_row(
    client,
    db_session: Session,
) -> None:
    _, _, system = _chain(
        db_session,
        suffix="QUERY",
        system_name="Query Stable System",
    )
    db_session.add_all(
        [
            Asset(hostname=f"query-asset-{index}", business_system_record=system)
            for index in range(12)
        ]
    )
    db_session.commit()
    statements: list[str] = []

    def count_statement(*args) -> None:
        statements.append(str(args[2]))

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        response = client.get("/api/v1/assets")
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)

    assert response.status_code == 200
    assert len(response.json()) == 12
    assert len(statements) <= 6


def test_single_and_bulk_binding_are_validated_atomic_and_audited(
    client,
    db_session: Session,
) -> None:
    _, _, active_system = _chain(
        db_session,
        suffix="ACTIVE",
        system_name="Active System",
    )
    _, _, draft_system = _chain(
        db_session,
        suffix="DRAFT",
        system_name="Draft System",
        status="draft",
    )
    first = Asset(hostname="asset-one")
    second = Asset(hostname="asset-two")
    db_session.add_all([first, second])
    db_session.commit()

    assigned = client.put(
        f"/api/v1/assets/{first.id}/business-system",
        json={"business_system_id": active_system.id},
    )
    assert assigned.status_code == 200
    assert assigned.json()["ownership"]["source"] == "manual"

    invalid = client.put(
        f"/api/v1/assets/{second.id}/business-system",
        json={"business_system_id": draft_system.id},
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "invalid_relationship"

    failed_batch = client.post(
        "/api/v1/assets/business-system-bindings",
        json={
            "asset_ids": [first.id, "missing-asset"],
            "business_system_id": None,
        },
    )
    assert failed_batch.status_code == 404
    db_session.refresh(first)
    assert first.business_system_id == active_system.id

    batch = client.post(
        "/api/v1/assets/business-system-bindings",
        json={
            "asset_ids": [first.id, second.id],
            "business_system_id": active_system.id,
        },
    )
    assert batch.status_code == 200
    assert batch.json()["updated_count"] == 1
    db_session.refresh(second)
    assert second.business_system_id == active_system.id
    audit_actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert "ownership.asset.assigned" in audit_actions
    assert "ownership.asset.bulk_assigned" in audit_actions

    unassigned = client.put(
        f"/api/v1/assets/{first.id}/business-system",
        json={"business_system_id": None},
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["ownership"]["status"] == "unassigned"


def test_legacy_metadata_writes_are_rejected_and_viewer_cannot_bind(
    client,
    db_session: Session,
) -> None:
    asset = Asset(hostname="protected-asset")
    db_session.add(asset)
    db_session.commit()
    legacy_write = client.patch(
        f"/api/v1/assets/{asset.id}",
        json={"business_system": "legacy override"},
    )
    assert legacy_write.status_code == 422

    viewer = User(
        username="asset-viewer",
        display_name="Asset Viewer",
        password_hash="unused",
        is_superuser=False,
        is_active=True,
    )
    db_session.add(viewer)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_current_user] = lambda: viewer
    try:
        with TestClient(app) as viewer_client:
            response = viewer_client.put(
                f"/api/v1/assets/{asset.id}/business-system",
                json={"business_system_id": None},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403


def test_agent_hint_matches_once_and_never_overwrites_manual_binding(
    client,
    db_session: Session,
) -> None:
    team = ResponsibilityTeam(
        code="SRE",
        name="sre",
        normalized_name="sre",
        status="active",
    )
    person = Person(name="alice", team=team, status="active")
    hinted_system = BusinessSystem(
        code="PAYMENTS",
        name="payments",
        normalized_name="payments",
        responsible_person=person,
        status="active",
    )
    db_session.add_all([team, person, hinted_system])
    db_session.commit()

    first_snapshot = client.post(
        "/api/v1/agents/snapshots",
        json=build_linux_snapshot(),
    )
    assert first_snapshot.status_code == 202
    asset_id = first_snapshot.json()["asset_id"]
    asset = db_session.get(Asset, asset_id)
    assert asset is not None
    assert asset.business_system_id == hinted_system.id
    assert asset.ownership_source == "agent_match"

    _, _, manual_system = _chain(
        db_session,
        suffix="MANUAL",
        system_name="Manual System",
    )
    manual_response = client.put(
        f"/api/v1/assets/{asset_id}/business-system",
        json={"business_system_id": manual_system.id},
    )
    assert manual_response.status_code == 200

    later_snapshot = build_linux_snapshot(
        nginx_version="1.26.2",
        collected_at="2026-05-05T13:00:00Z",
    )
    later_snapshot["business_system"] = "payments"
    assert client.post("/api/v1/agents/snapshots", json=later_snapshot).status_code == 202
    db_session.refresh(asset)
    assert asset.business_system_id == manual_system.id
    assert asset.ownership_source == "manual"


def test_legacy_migration_is_idempotent_and_marks_conflicts_draft(
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            Asset(
                hostname="pay-1",
                business_system=" 支付系统 ",
                owner_team="支付 SRE",
                owner_person="张三",
            ),
            Asset(
                hostname="pay-2",
                business_system="支付系统",
                owner_team="支付SRE",
                owner_person="张三",
            ),
            Asset(
                hostname="crm-1",
                business_system="CRM",
                owner_team="CRM Team A",
                owner_person="Alice",
            ),
            Asset(
                hostname="crm-2",
                business_system=" crm ",
                owner_team="CRM Team B",
                owner_person="Bob",
            ),
            Asset(hostname="no-system", owner_team="orphan team"),
        ]
    )
    db_session.commit()
    asset_count_before = db_session.scalar(select(func.count(Asset.id)))

    first = migrate_legacy_asset_ownership(db_session)
    assert first.created_team_count == 3
    assert first.created_person_count == 3
    assert first.created_system_count == 2
    assert first.bound_asset_count == 4
    assert first.unassigned_asset_count == 1
    assert first.conflicting_system_count == 1

    payment = db_session.scalar(
        select(BusinessSystem).where(BusinessSystem.normalized_name == "支付系统")
    )
    crm = db_session.scalar(
        select(BusinessSystem).where(BusinessSystem.normalized_name == "crm")
    )
    assert payment is not None and payment.status == "active"
    assert crm is not None and crm.status == "draft"
    assert all(
        asset.ownership_source == "migration"
        for asset in db_session.scalars(
            select(Asset).where(Asset.business_system_id.is_not(None))
        )
    )

    second = migrate_legacy_asset_ownership(db_session)
    assert second.created_team_count == 0
    assert second.created_person_count == 0
    assert second.created_system_count == 0
    assert second.bound_asset_count == 0
    assert second.unassigned_asset_count == 1
    assert db_session.scalar(select(func.count(Asset.id))) == asset_count_before


def test_legacy_migration_dry_run_rolls_back_and_keeps_legacy_fields(
    db_session: Session,
) -> None:
    asset = Asset(
        hostname="dry-run-asset",
        business_system="Dry Run System",
        owner_team="Dry Run Team",
        owner_person="Dry Run Owner",
    )
    db_session.add(asset)
    db_session.commit()
    asset_id = asset.id

    report = migrate_legacy_asset_ownership(db_session, commit=False)

    assert report.created_team_count == 1
    assert report.created_person_count == 1
    assert report.created_system_count == 1
    assert report.bound_asset_count == 1
    persisted_asset = db_session.get(Asset, asset_id)
    assert persisted_asset is not None
    assert persisted_asset.business_system_id is None
    assert persisted_asset.business_system == "Dry Run System"
    assert persisted_asset.owner_team == "Dry Run Team"
    assert persisted_asset.owner_person == "Dry Run Owner"
    assert db_session.scalar(select(func.count(BusinessSystem.id))) == 0
    assert db_session.scalar(select(func.count(Person.id))) == 0
    assert db_session.scalar(select(func.count(ResponsibilityTeam.id))) == 0
    assert db_session.scalar(select(func.count(Asset.id))) == 1
