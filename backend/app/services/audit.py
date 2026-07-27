from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AuditLog, MatchResult, MatchResultHandlingRecord
from app.schemas.audit import AuditLogOut, HandlingAuditRecordOut


SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "signature",
    "token",
)
REDACTED_VALUE = "[redacted]"


def create_audit_log(
    db: Session,
    *,
    action: str,
    resource_type: str,
    summary: str,
    resource_id: str | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
    outcome: str = "success",
    details: dict[str, object] | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        summary=summary,
        details_json=redact_audit_details(details or {}),
    )
    db.add(log)
    return log


def list_audit_logs(
    db: Session,
    *,
    action: str | None = None,
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
) -> list[AuditLogOut]:
    statement = select(AuditLog).order_by(desc(AuditLog.created_at))
    if action:
        statement = statement.where(AuditLog.action == action)
    if actor_id:
        statement = statement.where(AuditLog.actor_id == actor_id)
    if resource_type:
        statement = statement.where(AuditLog.resource_type == resource_type)
    if resource_id:
        statement = statement.where(AuditLog.resource_id == resource_id)
    if outcome:
        statement = statement.where(AuditLog.outcome == outcome)
    statement = statement.limit(limit)
    return [_to_audit_log_out(log) for log in db.scalars(statement).all()]


def list_handling_audit_records(
    db: Session,
    *,
    actor_id: str | None = None,
    match_result_id: str | None = None,
    to_status: str | None = None,
    action: str | None = None,
    limit: int = 100,
) -> list[HandlingAuditRecordOut]:
    statement = (
        select(MatchResultHandlingRecord)
        .join(MatchResult, MatchResultHandlingRecord.match_result_id == MatchResult.id)
        .options(
            selectinload(MatchResultHandlingRecord.match_result).selectinload(
                MatchResult.asset
            ),
            selectinload(MatchResultHandlingRecord.match_result).selectinload(
                MatchResult.vulnerability
            ),
        )
        .order_by(desc(MatchResultHandlingRecord.created_at))
    )
    if actor_id:
        statement = statement.where(MatchResultHandlingRecord.actor_id == actor_id)
    if match_result_id:
        statement = statement.where(
            MatchResultHandlingRecord.match_result_id == match_result_id
        )
    if to_status:
        statement = statement.where(MatchResultHandlingRecord.to_status == to_status)
    if action:
        statement = statement.where(MatchResultHandlingRecord.action == action)
    statement = statement.limit(limit)
    return [
        _to_handling_audit_record_out(record)
        for record in db.scalars(statement).all()
    ]


def redact_audit_details(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                redacted[str(key)] = REDACTED_VALUE
            else:
                redacted[str(key)] = redact_audit_details(item)
        return redacted
    if isinstance(value, list):
        return [redact_audit_details(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _to_audit_log_out(log: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=log.id,
        actor_type=log.actor_type,
        actor_id=log.actor_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        outcome=log.outcome,
        summary=log.summary,
        details=log.details_json or {},
        created_at=log.created_at,
    )


def _to_handling_audit_record_out(
    record: MatchResultHandlingRecord,
) -> HandlingAuditRecordOut:
    match_result = record.match_result
    vulnerability = match_result.vulnerability
    asset = match_result.asset
    return HandlingAuditRecordOut(
        id=record.id,
        match_result_id=record.match_result_id,
        risk_code=match_result.risk_code,
        vulnerability_id=vulnerability.id,
        vulnerability_canonical_id=vulnerability.canonical_id,
        vulnerability_title=vulnerability.title,
        asset_id=asset.id,
        asset_hostname=asset.hostname,
        action=record.action,
        from_status=record.from_status,
        to_status=record.to_status,
        note=record.note,
        actor_id=record.actor_id,
        actor_username=record.actor_username,
        actor_display_name=record.actor_display_name,
        created_at=record.created_at,
    )
