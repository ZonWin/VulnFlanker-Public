from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user
from app.api.routes import agent_downloads
from app.core.config import get_settings
from app.db.models import AgentStatus, User
from app.schemas.agent import (
    AgentDetail,
    AgentHeartbeatIn,
    AgentHeartbeatOut,
    AgentSummary,
    AssetSnapshotIn,
    AssetSnapshotSubmissionOut,
)
from app.schemas.verification import AgentTaskPollOut, AgentTaskResultIn, AgentTaskResultOut
from app.services.agent_ingestion import ingest_asset_snapshot, register_heartbeat
from app.services.agent_status import get_agent_status, list_agent_statuses
from app.services.verification_tasks import poll_next_agent_task, submit_agent_task_result

router = APIRouter()


def require_legacy_agent_api_enabled() -> None:
    if not get_settings().legacy_agent_api_enabled:
        raise HTTPException(status_code=404, detail="Legacy Agent API is disabled")


def ensure_legacy_agent_not_disabled(db: Session, agent_id: str) -> None:
    agent_status = db.scalar(
        select(AgentStatus.status).where(AgentStatus.agent_id == agent_id)
    )
    if agent_status == "disabled":
        raise HTTPException(status_code=403, detail="Agent is disabled")


legacy_agent_api = [Depends(require_legacy_agent_api_enabled)]
router.include_router(
    agent_downloads.router,
    prefix="/downloads",
    dependencies=legacy_agent_api,
)


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=legacy_agent_api,
)
async def heartbeat(
    payload: AgentHeartbeatIn,
    db: Session = Depends(get_db),
) -> AgentHeartbeatOut:
    ensure_legacy_agent_not_disabled(db, payload.agent_id)
    return register_heartbeat(db, payload)


@router.get("", response_model=list[AgentSummary])
async def get_agents(
    _: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> list[AgentSummary]:
    return list_agent_statuses(db)


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


@router.post(
    "/snapshots",
    response_model=AssetSnapshotSubmissionOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=legacy_agent_api,
)
async def submit_snapshot(
    payload: AssetSnapshotIn,
    db: Session = Depends(get_db),
) -> AssetSnapshotSubmissionOut:
    ensure_legacy_agent_not_disabled(db, payload.agent_id)
    return ingest_asset_snapshot(db, payload)


@router.get(
    "/{agent_id}/tasks/next",
    response_model=AgentTaskPollOut,
    dependencies=legacy_agent_api,
)
async def get_next_agent_task(
    agent_id: str,
    db: Session = Depends(get_db),
) -> AgentTaskPollOut:
    ensure_legacy_agent_not_disabled(db, agent_id)
    return poll_next_agent_task(db, agent_id)


@router.post(
    "/{agent_id}/tasks/{task_id}/results",
    response_model=AgentTaskResultOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=legacy_agent_api,
)
async def submit_agent_task_result_route(
    agent_id: str,
    task_id: str,
    payload: AgentTaskResultIn,
    db: Session = Depends(get_db),
) -> AgentTaskResultOut:
    ensure_legacy_agent_not_disabled(db, agent_id)
    result = submit_agent_task_result(
        db,
        agent_id=agent_id,
        task_id=task_id,
        payload=payload,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Agent task not found")
    return result
