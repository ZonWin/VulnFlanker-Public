from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_superuser
from app.db.models import User
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
    PersonUpdate,
    ResponsibilityTeamCreate,
    ResponsibilityTeamList,
    ResponsibilityTeamOut,
    ResponsibilityTeamUpdate,
    TransferMembersRequest,
    VersionedActionRequest,
)
from app.services import ownership as ownership_service
from app.services.ownership import OwnershipServiceError


router = APIRouter()


@router.get("/responsibility-teams", response_model=ResponsibilityTeamList)
async def get_responsibility_teams(
    keyword: str | None = Query(default=None, max_length=255),
    status: Literal["active", "inactive"] | None = Query(default=None),
    has_members: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort_by: Literal["code", "name", "status", "created_at", "updated_at"] = Query(
        default="updated_at"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    db: Session = Depends(get_db),
) -> ResponsibilityTeamList:
    return ownership_service.list_responsibility_teams(
        db,
        keyword=keyword,
        status=status,
        has_members=has_members,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post(
    "/responsibility-teams",
    response_model=ResponsibilityTeamOut,
    status_code=201,
)
async def post_responsibility_team(
    payload: ResponsibilityTeamCreate,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> ResponsibilityTeamOut:
    return _run(
        ownership_service.create_responsibility_team,
        db,
        payload,
        actor=actor,
    )


@router.get(
    "/responsibility-teams/{team_id}",
    response_model=ResponsibilityTeamOut,
)
async def get_responsibility_team(
    team_id: str,
    db: Session = Depends(get_db),
) -> ResponsibilityTeamOut:
    return _run(ownership_service.get_responsibility_team, db, team_id)


@router.patch(
    "/responsibility-teams/{team_id}",
    response_model=ResponsibilityTeamOut,
)
async def patch_responsibility_team(
    team_id: str,
    payload: ResponsibilityTeamUpdate,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> ResponsibilityTeamOut:
    return _run(
        ownership_service.update_responsibility_team,
        db,
        team_id,
        payload,
        actor=actor,
    )


@router.post(
    "/responsibility-teams/{team_id}/transfer-members",
    response_model=ResponsibilityTeamOut,
)
async def post_transfer_members(
    team_id: str,
    payload: TransferMembersRequest,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> ResponsibilityTeamOut:
    return _run(
        ownership_service.transfer_members,
        db,
        team_id,
        payload.person_ids,
        actor=actor,
    )


@router.post(
    "/responsibility-teams/{team_id}/activate",
    response_model=ResponsibilityTeamOut,
)
async def post_activate_team(
    team_id: str,
    payload: VersionedActionRequest,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> ResponsibilityTeamOut:
    return _run(
        ownership_service.activate_responsibility_team,
        db,
        team_id,
        expected_version=payload.expected_version,
        actor=actor,
    )


@router.post(
    "/responsibility-teams/{team_id}/deactivate",
    response_model=ResponsibilityTeamOut,
)
async def post_deactivate_team(
    team_id: str,
    payload: VersionedActionRequest,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> ResponsibilityTeamOut:
    return _run(
        ownership_service.deactivate_responsibility_team,
        db,
        team_id,
        expected_version=payload.expected_version,
        actor=actor,
    )


@router.get("/people", response_model=PersonList)
async def get_people(
    keyword: str | None = Query(default=None, max_length=255),
    team_id: str | None = Query(default=None, max_length=36),
    status: Literal["active", "inactive"] | None = Query(default=None),
    has_email: bool | None = Query(default=None),
    has_systems: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort_by: Literal["name", "employee_no", "status", "created_at", "updated_at"] = Query(
        default="updated_at"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    db: Session = Depends(get_db),
) -> PersonList:
    return ownership_service.list_people(
        db,
        keyword=keyword,
        team_id=team_id,
        status=status,
        has_email=has_email,
        has_systems=has_systems,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/people", response_model=PersonOut, status_code=201)
async def post_person(
    payload: PersonCreate,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> PersonOut:
    return _run(ownership_service.create_person, db, payload, actor=actor)


@router.get("/people/{person_id}", response_model=PersonOut)
async def get_person(
    person_id: str,
    db: Session = Depends(get_db),
) -> PersonOut:
    return _run(ownership_service.get_person, db, person_id)


@router.patch("/people/{person_id}", response_model=PersonOut)
async def patch_person(
    person_id: str,
    payload: PersonUpdate,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> PersonOut:
    return _run(ownership_service.update_person, db, person_id, payload, actor=actor)


@router.post("/people/{person_id}/activate", response_model=PersonOut)
async def post_activate_person(
    person_id: str,
    payload: VersionedActionRequest,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> PersonOut:
    return _run(
        ownership_service.activate_person,
        db,
        person_id,
        expected_version=payload.expected_version,
        actor=actor,
    )


@router.post("/people/{person_id}/deactivate", response_model=PersonOut)
async def post_deactivate_person(
    person_id: str,
    payload: PersonDeactivateRequest,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> PersonOut:
    return _run(
        ownership_service.deactivate_person,
        db,
        person_id,
        payload,
        actor=actor,
    )


@router.get("/business-systems", response_model=BusinessSystemList)
async def get_business_systems(
    keyword: str | None = Query(default=None, max_length=255),
    responsible_person_id: str | None = Query(default=None, max_length=36),
    team_id: str | None = Query(default=None, max_length=36),
    status: Literal["draft", "active", "inactive"] | None = Query(default=None),
    has_assets: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort_by: Literal["code", "name", "status", "created_at", "updated_at"] = Query(
        default="updated_at"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    db: Session = Depends(get_db),
) -> BusinessSystemList:
    return ownership_service.list_business_systems(
        db,
        keyword=keyword,
        responsible_person_id=responsible_person_id,
        team_id=team_id,
        status=status,
        has_assets=has_assets,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/business-systems", response_model=BusinessSystemOut, status_code=201)
async def post_business_system(
    payload: BusinessSystemCreate,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> BusinessSystemOut:
    return _run(ownership_service.create_business_system, db, payload, actor=actor)


@router.get("/business-systems/{system_id}", response_model=BusinessSystemOut)
async def get_business_system(
    system_id: str,
    db: Session = Depends(get_db),
) -> BusinessSystemOut:
    return _run(ownership_service.get_business_system, db, system_id)


@router.patch("/business-systems/{system_id}", response_model=BusinessSystemOut)
async def patch_business_system(
    system_id: str,
    payload: BusinessSystemUpdate,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> BusinessSystemOut:
    return _run(
        ownership_service.update_business_system,
        db,
        system_id,
        payload,
        actor=actor,
    )


@router.post("/business-systems/{system_id}/activate", response_model=BusinessSystemOut)
async def post_activate_business_system(
    system_id: str,
    payload: VersionedActionRequest,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> BusinessSystemOut:
    return _run(
        ownership_service.activate_business_system,
        db,
        system_id,
        expected_version=payload.expected_version,
        actor=actor,
    )


@router.post("/business-systems/{system_id}/deactivate", response_model=BusinessSystemOut)
async def post_deactivate_business_system(
    system_id: str,
    payload: BusinessSystemDeactivateRequest,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> BusinessSystemOut:
    return _run(
        ownership_service.deactivate_business_system,
        db,
        system_id,
        payload,
        actor=actor,
    )


@router.get("/ownership/summary", response_model=OwnershipSummary)
async def get_ownership_summary(
    db: Session = Depends(get_db),
) -> OwnershipSummary:
    return ownership_service.get_ownership_summary(db)


def _run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except OwnershipServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        ) from exc
