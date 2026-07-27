from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.audit import AuditLogOut, HandlingAuditRecordOut
from app.services.audit import list_audit_logs, list_handling_audit_records

router = APIRouter()


@router.get("/logs", response_model=list[AuditLogOut])
async def get_audit_logs(
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    return list_audit_logs(
        db,
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        limit=limit,
    )


@router.get("/handling-records", response_model=list[HandlingAuditRecordOut])
async def get_handling_audit_records(
    actor_id: str | None = Query(default=None),
    match_result_id: str | None = Query(default=None),
    to_status: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[HandlingAuditRecordOut]:
    return list_handling_audit_records(
        db,
        actor_id=actor_id,
        match_result_id=match_result_id,
        to_status=to_status,
        action=action,
        limit=limit,
    )
