from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import AgentStatus, Asset, AssetSnapshot, VerificationTask
from app.schemas.agent import (
    AgentDetail,
    AgentStatusOut,
    AgentSummary,
    AgentTaskStats,
    AgentHeartbeatIn,
    AssetSnapshotIn,
)
from app.schemas.asset import AssetFreshnessOut


AGENT_OFFLINE_AFTER_SECONDS = 300
SNAPSHOT_STALE_AFTER_SECONDS = 86_400


def record_agent_heartbeat(
    db: Session,
    payload: AgentHeartbeatIn,
    *,
    seen_at: datetime | None = None,
) -> AgentStatus:
    status = _get_or_create_agent_status(db, payload.agent_id)
    status.hostname = payload.hostname
    status.platform = payload.platform
    status.version = payload.version
    status.status = "online"
    status.last_heartbeat_at = seen_at or utcnow()
    status.last_error = None
    return status


def record_agent_snapshot(
    db: Session,
    payload: AssetSnapshotIn,
    *,
    received_at: datetime | None = None,
) -> AgentStatus:
    status = _get_or_create_agent_status(db, payload.agent_id)
    status.hostname = payload.hostname
    status.platform = payload.platform
    status.version = payload.agent_version
    status.status = "online"
    status.last_snapshot_at = received_at or utcnow()
    status.last_error = None
    return status


def record_agent_task_poll(
    db: Session,
    agent_id: str,
    *,
    seen_at: datetime | None = None,
) -> AgentStatus:
    status = _get_or_create_agent_status(db, agent_id)
    status.status = "online"
    status.last_task_poll_at = seen_at or utcnow()
    return status


def record_agent_task_result(
    db: Session,
    agent_id: str,
    *,
    result_status: str,
    error_message: str | None = None,
    seen_at: datetime | None = None,
) -> AgentStatus:
    status = _get_or_create_agent_status(db, agent_id)
    status.status = "online"
    status.last_task_poll_at = seen_at or utcnow()
    status.last_error = error_message if result_status in {"failed", "rejected"} else None
    return status


def list_agent_statuses(db: Session) -> list[AgentSummary]:
    statuses = db.scalars(
        select(AgentStatus).order_by(
            desc(AgentStatus.last_heartbeat_at),
            desc(AgentStatus.last_snapshot_at),
            desc(AgentStatus.updated_at),
            AgentStatus.agent_id,
        )
    ).all()
    return [_to_agent_summary(db, status) for status in statuses]


def get_agent_status(db: Session, agent_id: str) -> AgentDetail | None:
    status = db.scalar(select(AgentStatus).where(AgentStatus.agent_id == agent_id))
    if status is None:
        return None
    summary = _to_agent_summary(db, status)
    return AgentDetail(**summary.model_dump())


def get_asset_agent_status(db: Session, asset: Asset) -> AgentStatusOut | None:
    if not asset.agent_id:
        return None
    status = db.scalar(select(AgentStatus).where(AgentStatus.agent_id == asset.agent_id))
    if status is None:
        return None
    return _to_agent_status_out(status)


def build_asset_freshness(
    latest_snapshot: AssetSnapshot | None,
) -> AssetFreshnessOut:
    last_snapshot_at = latest_snapshot.received_at if latest_snapshot is not None else None
    snapshot_age_seconds = _age_seconds(last_snapshot_at)
    return AssetFreshnessOut(
        last_snapshot_at=last_snapshot_at,
        snapshot_age_seconds=snapshot_age_seconds,
        stale_after_seconds=SNAPSHOT_STALE_AFTER_SECONDS,
        is_stale=snapshot_age_seconds is None
        or snapshot_age_seconds > SNAPSHOT_STALE_AFTER_SECONDS,
    )


def _get_or_create_agent_status(db: Session, agent_id: str) -> AgentStatus:
    status = db.scalar(select(AgentStatus).where(AgentStatus.agent_id == agent_id))
    if status is not None:
        return status
    status = AgentStatus(agent_id=agent_id, status="unknown")
    db.add(status)
    db.flush()
    return status


def _to_agent_summary(db: Session, status: AgentStatus) -> AgentSummary:
    asset = db.scalar(select(Asset).where(Asset.agent_id == status.agent_id))
    task_stats = _task_stats(db, asset.id if asset is not None else None)
    base = _to_agent_status_out(status).model_dump()
    return AgentSummary(
        **base,
        asset_id=asset.id if asset is not None else None,
        asset_hostname=asset.hostname if asset is not None else None,
        asset_primary_ip=asset.primary_ip if asset is not None else None,
        asset_last_seen_at=asset.last_seen_at if asset is not None else None,
        task_stats=task_stats,
    )


def _to_agent_status_out(status: AgentStatus) -> AgentStatusOut:
    return AgentStatusOut(
        agent_id=status.agent_id,
        hostname=status.hostname,
        platform=status.platform,
        version=status.version,
        status=_computed_status(status),
        last_heartbeat_at=status.last_heartbeat_at,
        last_snapshot_at=status.last_snapshot_at,
        last_task_poll_at=status.last_task_poll_at,
        last_error=status.last_error,
        created_at=status.created_at,
        updated_at=status.updated_at,
    )


def compute_agent_status(status: AgentStatus) -> str:
    return _computed_status(status)


def _task_stats(db: Session, asset_id: str | None) -> AgentTaskStats:
    if asset_id is None:
        return AgentTaskStats()
    rows = db.execute(
        select(VerificationTask.status, func.count(VerificationTask.id))
        .where(VerificationTask.asset_id == asset_id)
        .group_by(VerificationTask.status)
    ).all()
    counts = {row[0]: row[1] for row in rows}
    return AgentTaskStats(
        queued=counts.get("queued", 0),
        in_progress=counts.get("in_progress", 0),
        cancel_requested=counts.get("cancel_requested", 0),
        cancelled=counts.get("cancelled", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        rejected=counts.get("rejected", 0),
        total=sum(counts.values()),
    )


def _computed_status(status: AgentStatus) -> str:
    if status.status == "disabled":
        return "disabled"
    latest_signal = _latest_signal(
        status.last_heartbeat_at,
        status.last_snapshot_at,
        status.last_task_poll_at,
    )
    if latest_signal is None:
        return status.status or "unknown"
    age_seconds = _age_seconds(latest_signal)
    if age_seconds is not None and age_seconds > AGENT_OFFLINE_AFTER_SECONDS:
        return "offline"
    return "online"


def _latest_signal(*timestamps: datetime | None) -> datetime | None:
    present = [_ensure_aware(value) for value in timestamps if value is not None]
    return max(present) if present else None


def _age_seconds(value: datetime | None) -> int | None:
    if value is None:
        return None
    delta = utcnow() - _ensure_aware(value)
    return max(0, int(delta.total_seconds()))


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
