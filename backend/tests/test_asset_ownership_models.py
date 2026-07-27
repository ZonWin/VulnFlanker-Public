from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Asset, BusinessSystem, Person, ResponsibilityTeam


def _team(*, code: str = "PAY-SRE", name: str = "支付 SRE") -> ResponsibilityTeam:
    return ResponsibilityTeam(
        code=code,
        name=name,
        normalized_name=name.casefold().replace(" ", ""),
    )


def test_ownership_relationship_chain_is_queryable(db_session: Session) -> None:
    team = _team()
    person = Person(
        employee_no="E1001",
        name="张三",
        email="zhangsan@example.com",
        team=team,
    )
    system = BusinessSystem(
        code="PAYMENT",
        name="支付系统",
        normalized_name="支付系统",
        responsible_person=person,
        status="active",
    )
    asset = Asset(
        hostname="pay-web-01",
        business_system_record=system,
        ownership_source="manual",
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    assert asset.business_system_record is not None
    assert asset.business_system_record.responsible_person is not None
    assert asset.business_system_record.responsible_person.team.name == "支付 SRE"
    assert person.business_systems == [system]
    assert system.assets == [asset]


def test_master_data_defaults_and_nullable_draft_owner(db_session: Session) -> None:
    team = _team()
    draft_system = BusinessSystem(
        code="LEGACY",
        name="待确认系统",
        normalized_name="待确认系统",
    )
    db_session.add_all([team, draft_system])
    db_session.commit()

    assert team.status == "active"
    assert team.version == 1
    assert draft_system.status == "draft"
    assert draft_system.responsible_person_id is None
    assert draft_system.version == 1


def test_team_code_and_normalized_name_are_unique(db_session: Session) -> None:
    db_session.add_all(
        [
            _team(),
            _team(code="OTHER", name="支付 SRE"),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_person_requires_team_id(db_session: Session) -> None:
    db_session.add(
        Person(
            employee_no="E404",
            name="无团队人员",
            team_id=None,  # type: ignore[arg-type]
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
