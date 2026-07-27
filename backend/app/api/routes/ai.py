from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_superuser
from app.db.models import User
from app.schemas.ai import (
    AIEnrichmentStatsOut,
    AIProfileCreate,
    AIProfileOut,
    AIProfileTestResult,
    AIProfileUpdate,
)
from app.services.ai_stats import get_ai_enrichment_stats
from app.services.ai_profiles import (
    create_ai_profile,
    delete_ai_profile,
    list_ai_profiles,
    test_ai_profile,
    update_ai_profile,
)
from app.services.auth import user_audit_details

router = APIRouter()


@router.get("/enrichment-stats", response_model=AIEnrichmentStatsOut)
async def enrichment_stats(
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AIEnrichmentStatsOut:
    return get_ai_enrichment_stats(db)


@router.get("/profiles", response_model=list[AIProfileOut])
async def list_profiles(
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> list[AIProfileOut]:
    return list_ai_profiles(db)


@router.post("/profiles", response_model=AIProfileOut)
async def create_profile(
    payload: AIProfileCreate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AIProfileOut:
    try:
        return create_ai_profile(
            db,
            payload,
            actor_id=current_user.id,
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/profiles/{profile_id}", response_model=AIProfileOut)
async def update_profile(
    profile_id: str,
    payload: AIProfileUpdate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AIProfileOut:
    try:
        return update_ai_profile(
            db,
            profile_id,
            payload,
            actor_id=current_user.id,
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/profiles/{profile_id}", response_model=AIProfileOut)
async def delete_profile(
    profile_id: str,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AIProfileOut:
    try:
        return delete_ai_profile(
            db,
            profile_id,
            actor_id=current_user.id,
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/profiles/{profile_id}/test", response_model=AIProfileTestResult)
async def test_profile(
    profile_id: str,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AIProfileTestResult:
    try:
        return test_ai_profile(
            db,
            profile_id,
            actor_id=current_user.id,
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
