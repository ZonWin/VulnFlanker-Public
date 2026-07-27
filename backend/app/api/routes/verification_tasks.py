from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user
from app.db.models import User
from app.schemas.verification import (
    VerificationTaskActionIn,
    VerificationTaskCreateIn,
    VerificationTaskDetailOut,
    VerificationTaskListPage,
    VerificationTaskOut,
    VerificationTaskSummaryOut,
)
from app.services.verification_tasks import (
    cancel_verification_task,
    create_verification_task,
    get_verification_task,
    list_verification_tasks,
    list_verification_tasks_page,
    retry_verification_task,
)
from app.services.auth import user_audit_details

router = APIRouter()


@router.get("", response_model=VerificationTaskListPage | list[VerificationTaskSummaryOut])
async def get_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    agent_id: str | None = Query(default=None),
    asset_id: str | None = Query(default=None),
    vulnerability_id: str | None = Query(default=None),
    match_result_id: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    paged: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=60, ge=1, le=300),
    db: Session = Depends(get_db),
) -> VerificationTaskListPage | list[VerificationTaskSummaryOut]:
    if not paged:
        return list_verification_tasks(
            db,
            status=status_filter,
            agent_id=agent_id,
            asset_id=asset_id,
            vulnerability_id=vulnerability_id,
            match_result_id=match_result_id,
            task_type=task_type,
            limit=limit,
        )
    return list_verification_tasks_page(
        db,
        status=status_filter,
        agent_id=agent_id,
        asset_id=asset_id,
        vulnerability_id=vulnerability_id,
        match_result_id=match_result_id,
        task_type=task_type,
        offset=offset,
        limit=limit,
    )


@router.post(
    "",
    response_model=VerificationTaskOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    payload: VerificationTaskCreateIn,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> VerificationTaskOut:
    try:
        task = create_verification_task(
            db,
            payload.model_copy(update={"requested_by": current_user.id}),
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Match result not found")
    return task


@router.get("/{task_id}", response_model=VerificationTaskDetailOut)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db),
) -> VerificationTaskDetailOut:
    task = get_verification_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Verification task not found")
    return task


@router.post("/{task_id}/cancel", response_model=VerificationTaskDetailOut)
async def cancel_task(
    task_id: str,
    payload: VerificationTaskActionIn | None = None,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> VerificationTaskDetailOut:
    try:
        task = cancel_verification_task(
            db,
            task_id,
            (payload or VerificationTaskActionIn()).model_copy(
                update={"requested_by": current_user.id}
            ),
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Verification task not found")
    return task


@router.post(
    "/{task_id}/retry",
    response_model=VerificationTaskOut,
    status_code=status.HTTP_201_CREATED,
)
async def retry_task(
    task_id: str,
    payload: VerificationTaskActionIn | None = None,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> VerificationTaskOut:
    try:
        task = retry_verification_task(
            db,
            task_id,
            (payload or VerificationTaskActionIn()).model_copy(
                update={"requested_by": current_user.id}
            ),
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Verification task not found")
    return task
