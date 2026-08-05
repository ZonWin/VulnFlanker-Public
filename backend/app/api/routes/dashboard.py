from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.dashboard import DashboardOverview
from app.services.dashboard import get_dashboard_overview


router = APIRouter()


@router.get("", response_model=DashboardOverview)
async def get_dashboard(
    days: int = Query(default=7, ge=1, le=366),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DashboardOverview:
    try:
        return get_dashboard_overview(
            db,
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
