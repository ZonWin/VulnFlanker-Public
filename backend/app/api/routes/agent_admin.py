from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user, require_superuser
from app.db.models import User
from app.schemas.agent import (
    AgentDetail,
    AgentEnrollmentTokenCreateIn,
    AgentEnrollmentTokenCreateOut,
    AgentEnrollmentTokenOut,
    AgentSummary,
    LifecycleActionOut,
)
from app.services.asset_lifecycle import delete_agent, disable_agent
from app.services.agent_auth import (
    create_enrollment_token,
    list_enrollment_tokens,
    revoke_enrollment_token,
)
from app.services.agent_status import get_agent_status, list_agent_statuses

router = APIRouter()


@router.get("", response_model=list[AgentSummary])
async def get_agents(
    _: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> list[AgentSummary]:
    return list_agent_statuses(db)


@router.get("/enrollment-tokens", response_model=list[AgentEnrollmentTokenOut])
async def list_agent_enrollment_tokens(
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> list[AgentEnrollmentTokenOut]:
    return list_enrollment_tokens(db)


@router.post(
    "/enrollment-tokens",
    response_model=AgentEnrollmentTokenCreateOut,
    status_code=201,
)
async def create_agent_enrollment_token(
    payload: AgentEnrollmentTokenCreateIn,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AgentEnrollmentTokenCreateOut:
    return create_enrollment_token(db, payload, created_by=current_user.id)


@router.post(
    "/enrollment-tokens/{token_id}/revoke",
    response_model=AgentEnrollmentTokenOut,
)
async def revoke_agent_enrollment_token(
    token_id: str,
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AgentEnrollmentTokenOut:
    token = revoke_enrollment_token(db, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Enrollment token not found")
    return token


@router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent_detail(
    agent_id: str,
    _: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> AgentDetail:
    agent = get_agent_status(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{agent_id}/disable", response_model=LifecycleActionOut)
async def disable_agent_route(
    agent_id: str,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> LifecycleActionOut:
    result = disable_agent(db, agent_id, actor_id=current_user.id)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return LifecycleActionOut(**result.__dict__)


@router.delete("/{agent_id}", response_model=LifecycleActionOut)
async def delete_agent_route(
    agent_id: str,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> LifecycleActionOut:
    result = delete_agent(db, agent_id, actor_id=current_user.id)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return LifecycleActionOut(**result.__dict__)
