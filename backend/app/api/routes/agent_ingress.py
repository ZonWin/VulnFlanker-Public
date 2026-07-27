from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.agent_deps import require_agent_identity
from app.api.deps import get_db
from app.schemas.agent import (
    AgentEnrollIn,
    AgentEnrollOut,
    AgentHeartbeatIn,
    AgentHeartbeatOut,
    AssetSnapshotIn,
    AssetSnapshotSubmissionOut,
)
from app.schemas.verification import AgentTaskPollOut, AgentTaskResultIn, AgentTaskResultOut
from app.services.agent_auth import AgentIdentity, enroll_agent
from app.services.agent_ingestion import ingest_asset_snapshot, register_heartbeat
from app.services.verification_tasks import poll_next_agent_task, submit_agent_task_result

router = APIRouter()


@router.post("/enroll", response_model=AgentEnrollOut, status_code=status.HTTP_201_CREATED)
async def enroll(
    payload: AgentEnrollIn,
    db: Session = Depends(get_db),
) -> AgentEnrollOut:
    result = enroll_agent(db, payload)
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid enrollment token")
    return result


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def heartbeat(
    payload: AgentHeartbeatIn,
    identity: AgentIdentity = Depends(require_agent_identity),
    db: Session = Depends(get_db),
) -> AgentHeartbeatOut:
    _ensure_payload_agent(payload.agent_id, identity)
    return register_heartbeat(db, payload)


@router.post(
    "/snapshots",
    response_model=AssetSnapshotSubmissionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_snapshot(
    payload: AssetSnapshotIn,
    identity: AgentIdentity = Depends(require_agent_identity),
    db: Session = Depends(get_db),
) -> AssetSnapshotSubmissionOut:
    _ensure_payload_agent(payload.agent_id, identity)
    return ingest_asset_snapshot(db, payload)


@router.get("/tasks/next", response_model=AgentTaskPollOut)
async def get_next_agent_task(
    identity: AgentIdentity = Depends(require_agent_identity),
    db: Session = Depends(get_db),
) -> AgentTaskPollOut:
    return poll_next_agent_task(db, identity.agent_id)


@router.post(
    "/tasks/{task_id}/results",
    response_model=AgentTaskResultOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_agent_task_result_route(
    task_id: str,
    payload: AgentTaskResultIn,
    identity: AgentIdentity = Depends(require_agent_identity),
    db: Session = Depends(get_db),
) -> AgentTaskResultOut:
    result = submit_agent_task_result(
        db,
        agent_id=identity.agent_id,
        task_id=task_id,
        payload=payload,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Agent task not found")
    return result


def _ensure_payload_agent(agent_id: str, identity: AgentIdentity) -> None:
    if agent_id != identity.agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent credential does not match payload agent_id",
        )
