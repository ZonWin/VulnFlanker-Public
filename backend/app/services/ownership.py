from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.db.base import utcnow
from app.db.models import Asset, BusinessSystem, Person, ResponsibilityTeam, User
from app.schemas.ownership import (
    BusinessSystemCreate,
    BusinessSystemDeactivateRequest,
    BusinessSystemList,
    BusinessSystemOut,
    BusinessSystemUpdate,
    OwnershipSummary,
    PersonCreate,
    PersonDeactivateRequest,
    PersonList,
    PersonOut,
    PersonSummary,
    PersonUpdate,
    ResponsibilityTeamCreate,
    ResponsibilityTeamList,
    ResponsibilityTeamOut,
    ResponsibilityTeamUpdate,
    SortOrder,
    TeamSummary,
)
from app.services.audit import create_audit_log


class OwnershipServiceError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def list_responsibility_teams(
    db: Session,
    *,
    keyword: str | None = None,
    status: str | None = None,
    has_members: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "updated_at",
    sort_order: SortOrder = "desc",
) -> ResponsibilityTeamList:
    person_count = (
        select(func.count(Person.id))
        .where(Person.team_id == ResponsibilityTeam.id)
        .correlate(ResponsibilityTeam)
        .scalar_subquery()
    )
    system_count = (
        select(func.count(BusinessSystem.id))
        .join(Person, BusinessSystem.responsible_person_id == Person.id)
        .where(Person.team_id == ResponsibilityTeam.id)
        .correlate(ResponsibilityTeam)
        .scalar_subquery()
    )
    asset_count = (
        select(func.count(Asset.id))
        .join(BusinessSystem, Asset.business_system_id == BusinessSystem.id)
        .join(Person, BusinessSystem.responsible_person_id == Person.id)
        .where(Person.team_id == ResponsibilityTeam.id)
        .correlate(ResponsibilityTeam)
        .scalar_subquery()
    )
    conditions = _team_conditions(keyword=keyword, status=status, has_members=has_members)
    total = db.scalar(
        select(func.count(ResponsibilityTeam.id)).where(*conditions)
    ) or 0
    sort_columns = {
        "code": ResponsibilityTeam.code,
        "name": ResponsibilityTeam.name,
        "status": ResponsibilityTeam.status,
        "created_at": ResponsibilityTeam.created_at,
        "updated_at": ResponsibilityTeam.updated_at,
    }
    order_column = sort_columns.get(sort_by, ResponsibilityTeam.updated_at)
    order = desc(order_column) if sort_order == "desc" else asc(order_column)
    rows = db.execute(
        select(
            ResponsibilityTeam,
            person_count.label("person_count"),
            system_count.label("business_system_count"),
            asset_count.label("asset_count"),
        )
        .where(*conditions)
        .order_by(order, ResponsibilityTeam.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ResponsibilityTeamList(
        items=[_team_out(team, *counts) for team, *counts in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_responsibility_team(db: Session, team_id: str) -> ResponsibilityTeamOut:
    team = db.get(ResponsibilityTeam, team_id)
    if team is None:
        raise _not_found("responsibility_team", team_id)
    person_count = db.scalar(
        select(func.count(Person.id)).where(Person.team_id == team.id)
    ) or 0
    system_count = db.scalar(
        select(func.count(BusinessSystem.id))
        .join(Person, BusinessSystem.responsible_person_id == Person.id)
        .where(Person.team_id == team.id)
    ) or 0
    asset_count = db.scalar(
        select(func.count(Asset.id))
        .join(BusinessSystem, Asset.business_system_id == BusinessSystem.id)
        .join(Person, BusinessSystem.responsible_person_id == Person.id)
        .where(Person.team_id == team.id)
    ) or 0
    return _team_out(team, person_count, system_count, asset_count)


def create_responsibility_team(
    db: Session,
    payload: ResponsibilityTeamCreate,
    *,
    actor: User,
) -> ResponsibilityTeamOut:
    team = ResponsibilityTeam(
        code=_normalize_code(payload.code),
        name=_clean_required(payload.name, "name"),
        normalized_name=_normalize_name(payload.name),
        description=_clean_optional(payload.description),
    )
    db.add(team)
    _flush(db, duplicate_message="Team code or name already exists.")
    _audit(
        db,
        actor=actor,
        action="ownership.team.created",
        resource_type="responsibility_team",
        resource_id=team.id,
        summary=f"Created responsibility team {team.code}.",
        details={"code": team.code, "name": team.name},
    )
    _commit(db, duplicate_message="Team code or name already exists.")
    return get_responsibility_team(db, team.id)


def update_responsibility_team(
    db: Session,
    team_id: str,
    payload: ResponsibilityTeamUpdate,
    *,
    actor: User,
) -> ResponsibilityTeamOut:
    team = _get_team_model(db, team_id)
    _check_version(team.version, payload.expected_version)
    before = {"name": team.name, "description": team.description}
    fields = payload.model_fields_set
    if "name" in fields and payload.name is not None:
        team.name = _clean_required(payload.name, "name")
        team.normalized_name = _normalize_name(payload.name)
    if "description" in fields:
        team.description = _clean_optional(payload.description)
    _audit(
        db,
        actor=actor,
        action="ownership.team.updated",
        resource_type="responsibility_team",
        resource_id=team.id,
        summary=f"Updated responsibility team {team.code}.",
        details={"before": before, "after": {"name": team.name, "description": team.description}},
    )
    _commit(db, duplicate_message="Team name already exists.")
    return get_responsibility_team(db, team.id)


def activate_responsibility_team(
    db: Session,
    team_id: str,
    *,
    expected_version: int,
    actor: User,
) -> ResponsibilityTeamOut:
    team = _get_team_model(db, team_id)
    _check_version(team.version, expected_version)
    team.status = "active"
    _audit_lifecycle(db, actor, "team", team.id, team.code, "activated")
    _commit(db)
    return get_responsibility_team(db, team.id)


def deactivate_responsibility_team(
    db: Session,
    team_id: str,
    *,
    expected_version: int,
    actor: User,
) -> ResponsibilityTeamOut:
    team = _get_team_model(db, team_id)
    _check_version(team.version, expected_version)
    active_people = db.scalar(
        select(func.count(Person.id)).where(
            Person.team_id == team.id,
            Person.status == "active",
        )
    ) or 0
    if active_people:
        raise OwnershipServiceError(
            "dependency_conflict",
            "Team still contains active people.",
            status_code=409,
            details={"active_person_count": active_people},
        )
    team.status = "inactive"
    _audit_lifecycle(db, actor, "team", team.id, team.code, "deactivated")
    _commit(db)
    return get_responsibility_team(db, team.id)


def transfer_members(
    db: Session,
    team_id: str,
    person_ids: Sequence[str],
    *,
    actor: User,
) -> ResponsibilityTeamOut:
    team = _get_team_model(db, team_id)
    if team.status != "active":
        raise _invalid_relationship("Members can only be transferred to an active team.")
    unique_ids = list(dict.fromkeys(person_ids))
    people = list(db.scalars(select(Person).where(Person.id.in_(unique_ids))).all())
    found_ids = {person.id for person in people}
    missing_ids = [person_id for person_id in unique_ids if person_id not in found_ids]
    if missing_ids:
        raise OwnershipServiceError(
            "resource_not_found",
            "One or more people were not found.",
            status_code=404,
            details={"missing_person_ids": missing_ids},
        )
    before_team_ids = {person.id: person.team_id for person in people}
    for person in people:
        person.team_id = team.id
    _audit(
        db,
        actor=actor,
        action="ownership.team.members_transferred",
        resource_type="responsibility_team",
        resource_id=team.id,
        summary=f"Transferred {len(people)} people to team {team.code}.",
        details={"person_ids": unique_ids, "before_team_ids": before_team_ids},
    )
    _commit(db)
    return get_responsibility_team(db, team.id)


def list_people(
    db: Session,
    *,
    keyword: str | None = None,
    team_id: str | None = None,
    status: str | None = None,
    has_email: bool | None = None,
    has_systems: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "updated_at",
    sort_order: SortOrder = "desc",
) -> PersonList:
    system_count = (
        select(func.count(BusinessSystem.id))
        .where(BusinessSystem.responsible_person_id == Person.id)
        .correlate(Person)
        .scalar_subquery()
    )
    asset_count = (
        select(func.count(Asset.id))
        .join(BusinessSystem, Asset.business_system_id == BusinessSystem.id)
        .where(BusinessSystem.responsible_person_id == Person.id)
        .correlate(Person)
        .scalar_subquery()
    )
    conditions = _person_conditions(
        keyword=keyword,
        team_id=team_id,
        status=status,
        has_email=has_email,
        has_systems=has_systems,
    )
    total = db.scalar(select(func.count(Person.id)).where(*conditions)) or 0
    sort_columns = {
        "name": Person.name,
        "employee_no": Person.employee_no,
        "status": Person.status,
        "created_at": Person.created_at,
        "updated_at": Person.updated_at,
    }
    order_column = sort_columns.get(sort_by, Person.updated_at)
    order = desc(order_column) if sort_order == "desc" else asc(order_column)
    rows = db.execute(
        select(
            Person,
            system_count.label("business_system_count"),
            asset_count.label("asset_count"),
        )
        .options(selectinload(Person.team))
        .where(*conditions)
        .order_by(order, Person.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PersonList(
        items=[_person_out(person, *counts) for person, *counts in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_person(db: Session, person_id: str) -> PersonOut:
    person = db.scalar(
        select(Person).options(selectinload(Person.team)).where(Person.id == person_id)
    )
    if person is None:
        raise _not_found("person", person_id)
    system_count, asset_count = _person_impact_counts(db, person.id)
    return _person_out(person, system_count, asset_count)


def create_person(db: Session, payload: PersonCreate, *, actor: User) -> PersonOut:
    team = _get_team_model(db, payload.team_id)
    if payload.status == "active" and team.status != "active":
        raise _invalid_relationship("Active people must belong to an active team.")
    if payload.user_id is not None and db.get(User, payload.user_id) is None:
        raise _not_found("user", payload.user_id)
    person = Person(
        employee_no=_clean_optional(payload.employee_no),
        name=_clean_required(payload.name, "name"),
        email=_clean_optional(payload.email),
        phone=_clean_optional(payload.phone),
        team_id=team.id,
        user_id=payload.user_id,
        notes=_clean_optional(payload.notes),
        status=payload.status,
    )
    db.add(person)
    _flush(db, duplicate_message="Employee number or linked user already exists.")
    _audit(
        db,
        actor=actor,
        action="ownership.person.created",
        resource_type="person",
        resource_id=person.id,
        summary=f"Created person {person.name}.",
        details={"name": person.name, "team_id": team.id},
    )
    _commit(db, duplicate_message="Employee number or linked user already exists.")
    return get_person(db, person.id)


def update_person(
    db: Session,
    person_id: str,
    payload: PersonUpdate,
    *,
    actor: User,
) -> PersonOut:
    person = _get_person_model(db, person_id)
    _check_version(person.version, payload.expected_version)
    fields = payload.model_fields_set
    before = _person_audit_snapshot(person)
    if "team_id" in fields and payload.team_id is not None:
        team = _get_team_model(db, payload.team_id)
        if person.status == "active" and team.status != "active":
            raise _invalid_relationship("Active people must belong to an active team.")
        person.team_id = team.id
    if "user_id" in fields:
        if payload.user_id is not None and db.get(User, payload.user_id) is None:
            raise _not_found("user", payload.user_id)
        person.user_id = payload.user_id
    if "employee_no" in fields:
        person.employee_no = _clean_optional(payload.employee_no)
    if "name" in fields and payload.name is not None:
        person.name = _clean_required(payload.name, "name")
    if "email" in fields:
        person.email = _clean_optional(payload.email)
    if "phone" in fields:
        person.phone = _clean_optional(payload.phone)
    if "notes" in fields:
        person.notes = _clean_optional(payload.notes)
    action = (
        "ownership.person.team_changed"
        if before["team_id"] != person.team_id
        else "ownership.person.updated"
    )
    system_count, asset_count = _person_impact_counts(db, person.id)
    _audit(
        db,
        actor=actor,
        action=action,
        resource_type="person",
        resource_id=person.id,
        summary=f"Updated person {person.name}.",
        details={
            "before": before,
            "after": _person_audit_snapshot(person),
            "affected_system_count": system_count,
            "affected_asset_count": asset_count,
        },
    )
    _commit(db, duplicate_message="Employee number or linked user already exists.")
    return get_person(db, person.id)


def activate_person(
    db: Session,
    person_id: str,
    *,
    expected_version: int,
    actor: User,
) -> PersonOut:
    person = _get_person_model(db, person_id)
    _check_version(person.version, expected_version)
    team = _get_team_model(db, person.team_id)
    if team.status != "active":
        raise _invalid_relationship("Person cannot be activated while the team is inactive.")
    person.status = "active"
    _audit_lifecycle(db, actor, "person", person.id, person.name, "activated")
    _commit(db)
    return get_person(db, person.id)


def deactivate_person(
    db: Session,
    person_id: str,
    payload: PersonDeactivateRequest,
    *,
    actor: User,
) -> PersonOut:
    person = _get_person_model(db, person_id)
    _check_version(person.version, payload.expected_version)
    active_systems = list(
        db.scalars(
            select(BusinessSystem).where(
                BusinessSystem.responsible_person_id == person.id,
                BusinessSystem.status == "active",
            )
        ).all()
    )
    replacement: Person | None = None
    if active_systems:
        if payload.replacement_person_id is None:
            asset_count = db.scalar(
                select(func.count(Asset.id))
                .join(BusinessSystem, Asset.business_system_id == BusinessSystem.id)
                .where(BusinessSystem.responsible_person_id == person.id)
            ) or 0
            raise OwnershipServiceError(
                "dependency_conflict",
                "Person still owns active business systems.",
                status_code=409,
                details={
                    "business_system_count": len(active_systems),
                    "asset_count": asset_count,
                },
            )
        replacement = _get_person_model(db, payload.replacement_person_id)
        _ensure_active_person(replacement)
        if replacement.id == person.id:
            raise _invalid_relationship("Replacement person must be different.")
        for system in active_systems:
            system.responsible_person_id = replacement.id
    person.status = "inactive"
    _audit(
        db,
        actor=actor,
        action="ownership.person.deactivated",
        resource_type="person",
        resource_id=person.id,
        summary=f"Deactivated person {person.name}.",
        details={
            "replacement_person_id": replacement.id if replacement else None,
            "reassigned_system_ids": [system.id for system in active_systems],
        },
    )
    _commit(db)
    return get_person(db, person.id)


def list_business_systems(
    db: Session,
    *,
    keyword: str | None = None,
    responsible_person_id: str | None = None,
    team_id: str | None = None,
    status: str | None = None,
    has_assets: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "updated_at",
    sort_order: SortOrder = "desc",
) -> BusinessSystemList:
    asset_count = (
        select(func.count(Asset.id))
        .where(Asset.business_system_id == BusinessSystem.id)
        .correlate(BusinessSystem)
        .scalar_subquery()
    )
    conditions = _system_conditions(
        keyword=keyword,
        responsible_person_id=responsible_person_id,
        team_id=team_id,
        status=status,
        has_assets=has_assets,
    )
    total = db.scalar(select(func.count(BusinessSystem.id)).where(*conditions)) or 0
    sort_columns = {
        "code": BusinessSystem.code,
        "name": BusinessSystem.name,
        "status": BusinessSystem.status,
        "created_at": BusinessSystem.created_at,
        "updated_at": BusinessSystem.updated_at,
    }
    order_column = sort_columns.get(sort_by, BusinessSystem.updated_at)
    order = desc(order_column) if sort_order == "desc" else asc(order_column)
    rows = db.execute(
        select(BusinessSystem, asset_count.label("asset_count"))
        .options(
            selectinload(BusinessSystem.responsible_person).selectinload(Person.team)
        )
        .where(*conditions)
        .order_by(order, BusinessSystem.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return BusinessSystemList(
        items=[_system_out(system, count) for system, count in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_business_system(db: Session, system_id: str) -> BusinessSystemOut:
    system = db.scalar(
        select(BusinessSystem)
        .options(
            selectinload(BusinessSystem.responsible_person).selectinload(Person.team)
        )
        .where(BusinessSystem.id == system_id)
    )
    if system is None:
        raise _not_found("business_system", system_id)
    asset_count = db.scalar(
        select(func.count(Asset.id)).where(Asset.business_system_id == system.id)
    ) or 0
    return _system_out(system, asset_count)


def create_business_system(
    db: Session,
    payload: BusinessSystemCreate,
    *,
    actor: User,
) -> BusinessSystemOut:
    person = (
        _get_person_model(db, payload.responsible_person_id)
        if payload.responsible_person_id
        else None
    )
    if payload.status == "active":
        if person is None:
            raise _invalid_relationship("Active business systems require a responsible person.")
        _ensure_active_person(person)
    system = BusinessSystem(
        code=_normalize_code(payload.code),
        name=_clean_required(payload.name, "name"),
        normalized_name=_normalize_name(payload.name),
        description=_clean_optional(payload.description),
        responsible_person_id=person.id if person else None,
        status=payload.status,
    )
    db.add(system)
    _flush(db, duplicate_message="Business system code or name already exists.")
    _audit(
        db,
        actor=actor,
        action="ownership.system.created",
        resource_type="business_system",
        resource_id=system.id,
        summary=f"Created business system {system.code}.",
        details={
            "code": system.code,
            "name": system.name,
            "responsible_person_id": system.responsible_person_id,
            "status": system.status,
        },
    )
    _commit(db, duplicate_message="Business system code or name already exists.")
    return get_business_system(db, system.id)


def update_business_system(
    db: Session,
    system_id: str,
    payload: BusinessSystemUpdate,
    *,
    actor: User,
) -> BusinessSystemOut:
    system = _get_system_model(db, system_id)
    _check_version(system.version, payload.expected_version)
    before = _system_audit_snapshot(system)
    fields = payload.model_fields_set
    if "name" in fields and payload.name is not None:
        system.name = _clean_required(payload.name, "name")
        system.normalized_name = _normalize_name(payload.name)
    if "description" in fields:
        system.description = _clean_optional(payload.description)
    if "responsible_person_id" in fields:
        person = (
            _get_person_model(db, payload.responsible_person_id)
            if payload.responsible_person_id
            else None
        )
        if system.status == "active":
            if person is None:
                raise _invalid_relationship(
                    "Active business systems require a responsible person."
                )
            _ensure_active_person(person)
        system.responsible_person_id = person.id if person else None
    asset_count = db.scalar(
        select(func.count(Asset.id)).where(Asset.business_system_id == system.id)
    ) or 0
    owner_changed = before["responsible_person_id"] != system.responsible_person_id
    _audit(
        db,
        actor=actor,
        action=(
            "ownership.system.owner_changed"
            if owner_changed
            else "ownership.system.updated"
        ),
        resource_type="business_system",
        resource_id=system.id,
        summary=f"Updated business system {system.code}.",
        details={
            "before": before,
            "after": _system_audit_snapshot(system),
            "affected_asset_count": asset_count,
        },
    )
    _commit(db, duplicate_message="Business system name already exists.")
    return get_business_system(db, system.id)


def activate_business_system(
    db: Session,
    system_id: str,
    *,
    expected_version: int,
    actor: User,
) -> BusinessSystemOut:
    system = _get_system_model(db, system_id)
    _check_version(system.version, expected_version)
    if system.responsible_person_id is None:
        raise _invalid_relationship("Business system has no responsible person.")
    person = _get_person_model(db, system.responsible_person_id)
    _ensure_active_person(person)
    system.status = "active"
    _audit_lifecycle(db, actor, "system", system.id, system.code, "activated")
    _commit(db)
    return get_business_system(db, system.id)


def deactivate_business_system(
    db: Session,
    system_id: str,
    payload: BusinessSystemDeactivateRequest,
    *,
    actor: User,
) -> BusinessSystemOut:
    system = _get_system_model(db, system_id)
    _check_version(system.version, payload.expected_version)
    assets = list(db.scalars(select(Asset).where(Asset.business_system_id == system.id)).all())
    replacement: BusinessSystem | None = None
    if assets:
        if payload.replacement_system_id and payload.unassign_assets:
            raise _invalid_relationship(
                "Choose either a replacement system or unassign_assets, not both."
            )
        if payload.replacement_system_id:
            replacement = _get_system_model(db, payload.replacement_system_id)
            if replacement.id == system.id or replacement.status != "active":
                raise _invalid_relationship("Replacement system must be a different active system.")
        elif not payload.unassign_assets:
            raise OwnershipServiceError(
                "dependency_conflict",
                "Business system still contains assets.",
                status_code=409,
                details={"asset_count": len(assets)},
            )
        changed_at = utcnow()
        for asset in assets:
            asset.business_system_id = replacement.id if replacement else None
            asset.ownership_source = "manual"
            asset.ownership_updated_at = changed_at
    system.status = "inactive"
    _audit(
        db,
        actor=actor,
        action="ownership.system.deactivated",
        resource_type="business_system",
        resource_id=system.id,
        summary=f"Deactivated business system {system.code}.",
        details={
            "affected_asset_ids": [asset.id for asset in assets],
            "replacement_system_id": replacement.id if replacement else None,
            "unassigned": bool(assets and replacement is None),
        },
    )
    _commit(db)
    return get_business_system(db, system.id)


def get_ownership_summary(db: Session) -> OwnershipSummary:
    team_count = db.scalar(select(func.count(ResponsibilityTeam.id))) or 0
    person_count = db.scalar(select(func.count(Person.id))) or 0
    system_count = db.scalar(select(func.count(BusinessSystem.id))) or 0
    asset_count = db.scalar(select(func.count(Asset.id))) or 0
    unassigned = db.scalar(
        select(func.count(Asset.id)).where(Asset.business_system_id.is_(None))
    ) or 0
    complete = db.scalar(
        select(func.count(Asset.id))
        .join(BusinessSystem, Asset.business_system_id == BusinessSystem.id)
        .join(Person, BusinessSystem.responsible_person_id == Person.id)
        .join(ResponsibilityTeam, Person.team_id == ResponsibilityTeam.id)
        .where(
            BusinessSystem.status == "active",
            Person.status == "active",
            ResponsibilityTeam.status == "active",
        )
    ) or 0
    return OwnershipSummary(
        team_count=team_count,
        person_count=person_count,
        business_system_count=system_count,
        asset_count=asset_count,
        complete_asset_count=complete,
        unassigned_asset_count=unassigned,
        incomplete_asset_count=max(asset_count - unassigned - complete, 0),
    )


def _team_conditions(
    *, keyword: str | None, status: str | None, has_members: bool | None
) -> list[Any]:
    conditions: list[Any] = []
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        conditions.append(
            or_(ResponsibilityTeam.code.ilike(pattern), ResponsibilityTeam.name.ilike(pattern))
        )
    if status:
        conditions.append(ResponsibilityTeam.status == status)
    if has_members is not None:
        member_exists = select(Person.id).where(Person.team_id == ResponsibilityTeam.id).exists()
        conditions.append(member_exists if has_members else ~member_exists)
    return conditions


def _person_conditions(
    *,
    keyword: str | None,
    team_id: str | None,
    status: str | None,
    has_email: bool | None,
    has_systems: bool | None,
) -> list[Any]:
    conditions: list[Any] = []
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        conditions.append(
            or_(
                Person.name.ilike(pattern),
                Person.employee_no.ilike(pattern),
                Person.email.ilike(pattern),
            )
        )
    if team_id:
        conditions.append(Person.team_id == team_id)
    if status:
        conditions.append(Person.status == status)
    if has_email is not None:
        conditions.append(Person.email.is_not(None) if has_email else Person.email.is_(None))
    if has_systems is not None:
        system_exists = (
            select(BusinessSystem.id)
            .where(BusinessSystem.responsible_person_id == Person.id)
            .exists()
        )
        conditions.append(system_exists if has_systems else ~system_exists)
    return conditions


def _system_conditions(
    *,
    keyword: str | None,
    responsible_person_id: str | None,
    team_id: str | None,
    status: str | None,
    has_assets: bool | None,
) -> list[Any]:
    conditions: list[Any] = []
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        conditions.append(
            or_(BusinessSystem.code.ilike(pattern), BusinessSystem.name.ilike(pattern))
        )
    if responsible_person_id:
        conditions.append(BusinessSystem.responsible_person_id == responsible_person_id)
    if team_id:
        team_person_ids = select(Person.id).where(Person.team_id == team_id)
        conditions.append(BusinessSystem.responsible_person_id.in_(team_person_ids))
    if status:
        conditions.append(BusinessSystem.status == status)
    if has_assets is not None:
        asset_exists = select(Asset.id).where(Asset.business_system_id == BusinessSystem.id).exists()
        conditions.append(asset_exists if has_assets else ~asset_exists)
    return conditions


def _get_team_model(db: Session, team_id: str) -> ResponsibilityTeam:
    team = db.get(ResponsibilityTeam, team_id)
    if team is None:
        raise _not_found("responsibility_team", team_id)
    return team


def _get_person_model(db: Session, person_id: str) -> Person:
    person = db.get(Person, person_id)
    if person is None:
        raise _not_found("person", person_id)
    return person


def _get_system_model(db: Session, system_id: str) -> BusinessSystem:
    system = db.get(BusinessSystem, system_id)
    if system is None:
        raise _not_found("business_system", system_id)
    return system


def _person_impact_counts(db: Session, person_id: str) -> tuple[int, int]:
    system_count = db.scalar(
        select(func.count(BusinessSystem.id)).where(
            BusinessSystem.responsible_person_id == person_id
        )
    ) or 0
    asset_count = db.scalar(
        select(func.count(Asset.id))
        .join(BusinessSystem, Asset.business_system_id == BusinessSystem.id)
        .where(BusinessSystem.responsible_person_id == person_id)
    ) or 0
    return system_count, asset_count


def _ensure_active_person(person: Person) -> None:
    if person.status != "active" or person.team.status != "active":
        raise _invalid_relationship("Responsible person and team must both be active.")


def _team_out(
    team: ResponsibilityTeam,
    person_count: int,
    business_system_count: int,
    asset_count: int,
) -> ResponsibilityTeamOut:
    return ResponsibilityTeamOut(
        id=team.id,
        code=team.code,
        name=team.name,
        description=team.description,
        status=team.status,  # type: ignore[arg-type]
        version=team.version,
        person_count=person_count,
        business_system_count=business_system_count,
        asset_count=asset_count,
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


def _team_summary(team: ResponsibilityTeam) -> TeamSummary:
    return TeamSummary(
        id=team.id,
        code=team.code,
        name=team.name,
        status=team.status,  # type: ignore[arg-type]
    )


def _person_out(person: Person, business_system_count: int, asset_count: int) -> PersonOut:
    return PersonOut(
        id=person.id,
        employee_no=person.employee_no,
        name=person.name,
        email=person.email,
        phone=person.phone,
        team=_team_summary(person.team),
        user_id=person.user_id,
        notes=person.notes,
        status=person.status,  # type: ignore[arg-type]
        version=person.version,
        business_system_count=business_system_count,
        asset_count=asset_count,
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


def _person_summary(person: Person) -> PersonSummary:
    return PersonSummary(
        id=person.id,
        employee_no=person.employee_no,
        name=person.name,
        email=person.email,
        status=person.status,  # type: ignore[arg-type]
        team=_team_summary(person.team),
    )


def _system_out(system: BusinessSystem, asset_count: int) -> BusinessSystemOut:
    return BusinessSystemOut(
        id=system.id,
        code=system.code,
        name=system.name,
        description=system.description,
        responsible_person=(
            _person_summary(system.responsible_person)
            if system.responsible_person is not None
            else None
        ),
        status=system.status,  # type: ignore[arg-type]
        version=system.version,
        asset_count=asset_count,
        created_at=system.created_at,
        updated_at=system.updated_at,
    )


def _normalize_code(value: str) -> str:
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).upper()
    if not normalized:
        raise OwnershipServiceError("validation_error", "code cannot be empty.")
    return normalized


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def _clean_required(value: str, label: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        raise OwnershipServiceError("validation_error", f"{label} cannot be empty.")
    return normalized


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    return normalized or None


def _check_version(actual: int, expected: int) -> None:
    if actual != expected:
        raise OwnershipServiceError(
            "stale_version",
            "The resource was modified by another request.",
            status_code=409,
            details={"expected_version": expected, "current_version": actual},
        )


def _commit(
    db: Session,
    *,
    duplicate_message: str = "A unique value already exists.",
) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise OwnershipServiceError(
            "duplicate_code",
            duplicate_message,
            status_code=409,
        ) from exc


def _flush(db: Session, *, duplicate_message: str) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise OwnershipServiceError(
            "duplicate_code",
            duplicate_message,
            status_code=409,
        ) from exc
    except StaleDataError as exc:
        db.rollback()
        raise OwnershipServiceError(
            "stale_version",
            "The resource was modified by another request.",
            status_code=409,
        ) from exc


def _not_found(resource_type: str, resource_id: str) -> OwnershipServiceError:
    return OwnershipServiceError(
        "resource_not_found",
        f"{resource_type} not found.",
        status_code=404,
        details={"resource_type": resource_type, "resource_id": resource_id},
    )


def _invalid_relationship(message: str) -> OwnershipServiceError:
    return OwnershipServiceError("invalid_relationship", message, status_code=400)


def _person_audit_snapshot(person: Person) -> dict[str, object]:
    return {
        "employee_no": person.employee_no,
        "name": person.name,
        "email": person.email,
        "phone": person.phone,
        "team_id": person.team_id,
        "user_id": person.user_id,
    }


def _system_audit_snapshot(system: BusinessSystem) -> dict[str, object]:
    return {
        "name": system.name,
        "description": system.description,
        "responsible_person_id": system.responsible_person_id,
        "status": system.status,
    }


def _audit_lifecycle(
    db: Session,
    actor: User,
    resource_name: str,
    resource_id: str,
    display_name: str,
    lifecycle_action: str,
) -> None:
    _audit(
        db,
        actor=actor,
        action=f"ownership.{resource_name}.{lifecycle_action}",
        resource_type=(
            "business_system" if resource_name == "system" else resource_name
        ),
        resource_id=resource_id,
        summary=f"{lifecycle_action.title()} {resource_name} {display_name}.",
        details={
            "status": "active" if lifecycle_action == "activated" else "inactive"
        },
    )


def _audit(
    db: Session,
    *,
    actor: User,
    action: str,
    resource_type: str,
    resource_id: str,
    summary: str,
    details: dict[str, object],
) -> None:
    create_audit_log(
        db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_type="user",
        actor_id=actor.id,
        outcome="success",
        summary=summary,
        details={
            "actor_username": actor.username,
            "actor_display_name": actor.display_name,
            **details,
        },
    )
