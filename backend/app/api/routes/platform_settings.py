from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user
from app.db.models import User
from app.schemas.platform_settings import PlatformSettingsOut, PlatformSettingsUpdate
from app.services.auth import user_audit_details
from app.services.platform_settings import (
    get_platform_settings_out,
    reset_platform_settings,
    update_platform_settings,
)

router = APIRouter()


@router.get("", response_model=PlatformSettingsOut)
async def get_platform_branding(
    db: Session = Depends(get_db),
) -> PlatformSettingsOut:
    return get_platform_settings_out(db)


@router.patch("", response_model=PlatformSettingsOut)
async def update_platform_branding(
    payload: PlatformSettingsUpdate,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> PlatformSettingsOut:
    try:
        return update_platform_settings(
            db,
            payload,
            actor_id=current_user.id,
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reset", response_model=PlatformSettingsOut)
async def reset_platform_branding(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> PlatformSettingsOut:
    return reset_platform_settings(
        db,
        actor_id=current_user.id,
        actor_details=user_audit_details(current_user),
    )
