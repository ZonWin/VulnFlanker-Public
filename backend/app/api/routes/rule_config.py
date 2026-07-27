from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user
from app.db.models import User
from app.schemas.rule_numeric_config import (
    RuleNumericConfigOut,
    RuleNumericConfigUpdate,
)
from app.services.rule_numeric_config import (
    get_rule_numeric_config_out,
    reset_rule_numeric_config,
    update_rule_numeric_config,
)
from app.services.auth import user_audit_details

router = APIRouter()


@router.get("", response_model=RuleNumericConfigOut)
async def get_rule_config(
    db: Session = Depends(get_db),
) -> RuleNumericConfigOut:
    return get_rule_numeric_config_out(db)


@router.patch("", response_model=RuleNumericConfigOut)
async def update_rule_config(
    payload: RuleNumericConfigUpdate,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> RuleNumericConfigOut:
    try:
        return update_rule_numeric_config(
            db,
            payload,
            actor_id=current_user.id,
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reset", response_model=RuleNumericConfigOut)
async def reset_rule_config(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> RuleNumericConfigOut:
    return reset_rule_numeric_config(
        db,
        actor_id=current_user.id,
        actor_details=user_audit_details(current_user),
    )
