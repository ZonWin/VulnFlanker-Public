from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import MatchResult, MatchResultHandlingRecord
from app.schemas.match_result import (
    MatchResultHandlingReopenIn,
    MatchResultHandlingUpdateIn,
)
from app.services.audit import create_audit_log


DEFAULT_HANDLING_STATUS = "unprocessed"
HANDLING_STATUSES = (
    DEFAULT_HANDLING_STATUS,
    "notified",
    "remediating",
    "pending_review",
    "resolved",
    "false_positive",
    "risk_accepted",
)
OPEN_HANDLING_STATUSES = (
    DEFAULT_HANDLING_STATUS,
    "notified",
    "remediating",
    "pending_review",
)
CLOSED_HANDLING_STATUSES = (
    "resolved",
    "false_positive",
    "risk_accepted",
)


def is_closed_handling_status(status: str | None) -> bool:
    return status in CLOSED_HANDLING_STATUSES


def update_match_result_handling(
    db: Session,
    match_result_id: str,
    payload: MatchResultHandlingUpdateIn,
    *,
    actor_id: str,
    actor_details: dict[str, object | None] | None = None,
) -> MatchResult | None:
    result = db.scalar(select(MatchResult).where(MatchResult.id == match_result_id))
    if result is None:
        return None

    previous_status = result.handling_status or DEFAULT_HANDLING_STATUS
    note = _normalize_note(payload.note)
    now = utcnow()
    result.handling_status = payload.handling_status
    result.handling_note = note
    result.handling_updated_by = actor_id
    result.handling_updated_at = now
    result.handling_closed_at = now if is_closed_handling_status(payload.handling_status) else None

    record = _append_record(
        result,
        action="status_changed",
        from_status=previous_status,
        to_status=payload.handling_status,
        note=note,
        actor_id=actor_id,
        actor_details=actor_details,
    )
    db.add(result)
    db.flush()
    create_audit_log(
        db,
        action="match_result.handling_updated",
        resource_type="match_result",
        resource_id=result.id,
        actor_type="user",
        actor_id=actor_id,
        outcome="success",
        summary="Updated manual handling status for match result.",
        details={
            **(actor_details or {}),
            "asset_id": result.asset_id,
            "vulnerability_id": result.vulnerability_id,
            "previous_handling_status": previous_status,
            "new_handling_status": result.handling_status,
            "note": note,
            "handling_record_id": record.id,
        },
    )
    db.commit()
    db.refresh(result)
    return result


def reopen_match_result_handling(
    db: Session,
    match_result_id: str,
    payload: MatchResultHandlingReopenIn,
    *,
    actor_id: str,
    actor_details: dict[str, object | None] | None = None,
) -> MatchResult | None:
    result = db.scalar(select(MatchResult).where(MatchResult.id == match_result_id))
    if result is None:
        return None

    previous_status = result.handling_status or DEFAULT_HANDLING_STATUS
    if not is_closed_handling_status(previous_status):
        raise ValueError("Only closed match result handling items can be reopened.")

    note = _normalize_note(payload.note)
    result.handling_status = DEFAULT_HANDLING_STATUS
    result.handling_note = note
    result.handling_updated_by = actor_id
    result.handling_updated_at = utcnow()
    result.handling_closed_at = None

    record = _append_record(
        result,
        action="reopened",
        from_status=previous_status,
        to_status=DEFAULT_HANDLING_STATUS,
        note=note,
        actor_id=actor_id,
        actor_details=actor_details,
    )
    db.add(result)
    db.flush()
    create_audit_log(
        db,
        action="match_result.handling_reopened",
        resource_type="match_result",
        resource_id=result.id,
        actor_type="user",
        actor_id=actor_id,
        outcome="success",
        summary="Reopened manual handling for match result.",
        details={
            **(actor_details or {}),
            "asset_id": result.asset_id,
            "vulnerability_id": result.vulnerability_id,
            "previous_handling_status": previous_status,
            "new_handling_status": result.handling_status,
            "note": note,
            "handling_record_id": record.id,
        },
    )
    db.commit()
    db.refresh(result)
    return result


def reopen_reappeared_match_result(
    db: Session,
    result: MatchResult,
) -> MatchResult:
    previous_status = result.handling_status or DEFAULT_HANDLING_STATUS
    if not is_closed_handling_status(previous_status):
        return result
    result.handling_status = DEFAULT_HANDLING_STATUS
    result.handling_note = "风险在后续评估中重新出现，系统已自动重新打开。"
    result.handling_updated_by = None
    result.handling_updated_at = utcnow()
    result.handling_closed_at = None
    record = _append_record(
        result,
        action="risk_reappeared",
        from_status=previous_status,
        to_status=DEFAULT_HANDLING_STATUS,
        note=result.handling_note,
        actor_id=None,
        actor_details=None,
    )
    db.add(result)
    db.flush()
    create_audit_log(
        db,
        action="match_result.risk_reappeared",
        resource_type="match_result",
        resource_id=result.id,
        actor_type="system",
        outcome="success",
        summary="Reopened a closed match result after the risk reappeared.",
        details={
            "asset_id": result.asset_id,
            "vulnerability_id": result.vulnerability_id,
            "previous_handling_status": previous_status,
            "new_handling_status": result.handling_status,
            "handling_record_id": record.id,
        },
    )
    return result


def _append_record(
    result: MatchResult,
    *,
    action: str,
    from_status: str | None,
    to_status: str,
    note: str | None,
    actor_id: str | None,
    actor_details: dict[str, object | None] | None,
) -> MatchResultHandlingRecord:
    details = actor_details or {}
    record = MatchResultHandlingRecord(
        action=action,
        from_status=from_status,
        to_status=to_status,
        note=note,
        actor_id=actor_id,
        actor_username=_detail_text(details.get("actor_username")),
        actor_display_name=_detail_text(details.get("actor_display_name")),
    )
    result.handling_records.append(record)
    return record


def _normalize_note(note: str | None) -> str | None:
    normalized = note.strip() if note is not None else None
    return normalized or None


def _detail_text(value: object | None) -> str | None:
    return str(value) if value else None
