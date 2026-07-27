from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.task_center import (
    TaskCenterItemOut,
    TaskCenterItemType,
    TaskCenterStatusGroup,
    TaskCenterSummaryOut,
)
from app.services.task_center import get_task_center_summary, list_task_center_items

router = APIRouter()


@router.get("/summary", response_model=TaskCenterSummaryOut)
async def get_summary(db: Session = Depends(get_db)) -> TaskCenterSummaryOut:
    return get_task_center_summary(db)


@router.get("/items", response_model=list[TaskCenterItemOut])
async def get_items(
    item_type: TaskCenterItemType | None = Query(default=None),
    status_group: TaskCenterStatusGroup | None = Query(default=None),
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    trigger_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[TaskCenterItemOut]:
    return list_task_center_items(
        db,
        item_type=item_type,
        status_group=status_group,
        status=status,
        source=source,
        trigger_type=trigger_type,
        keyword=keyword,
        limit=limit,
    )
