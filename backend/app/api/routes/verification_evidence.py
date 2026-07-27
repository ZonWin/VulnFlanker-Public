from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.verification import VerificationEvidenceSummaryOut
from app.services.verification_tasks import list_verification_evidence

router = APIRouter()


@router.get("", response_model=list[VerificationEvidenceSummaryOut])
async def get_verification_evidence(
    verification_task_id: str | None = Query(default=None),
    match_result_id: str | None = Query(default=None),
    asset_id: str | None = Query(default=None),
    vulnerability_id: str | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[VerificationEvidenceSummaryOut]:
    return list_verification_evidence(
        db,
        verification_task_id=verification_task_id,
        match_result_id=match_result_id,
        asset_id=asset_id,
        vulnerability_id=vulnerability_id,
        evidence_type=evidence_type,
        limit=limit,
    )
