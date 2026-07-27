from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import (
    AgentAuthEvent,
    AgentCredential,
    AgentStatus,
    Asset,
    AssetComponent,
    AssetExposure,
    AssetFirewall,
    AssetSnapshot,
    MatchEvidence,
    MatchResult,
    MatchResultHandlingRecord,
    VerificationEvidence,
    VerificationTask,
)
from app.services.audit import create_audit_log


@dataclass(frozen=True)
class LifecycleActionResult:
    status: str
    agent_id: str | None = None
    asset_id: str | None = None
    asset_deleted: bool = False
    agent_deleted: bool = False
    agent_disabled: bool = False
    match_results_deleted: int = 0
    verification_tasks_deleted: int = 0


def disable_agent(
    db: Session,
    agent_id: str,
    *,
    actor_id: str | None = None,
) -> LifecycleActionResult | None:
    status = _find_agent_status(db, agent_id)
    credentials = list(
        db.scalars(select(AgentCredential).where(AgentCredential.agent_id == agent_id))
    )
    if status is None and not credentials:
        return None

    now = utcnow()
    for credential in credentials:
        credential.status = "disabled"
        credential.revoked_at = credential.revoked_at or now
        db.add(credential)
    if status is not None:
        status.status = "disabled"
        status.last_error = "Agent disabled by operator."
        db.add(status)

    create_audit_log(
        db,
        action="agent.disabled",
        resource_type="agent",
        resource_id=agent_id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        summary=f"Disabled Agent {agent_id}.",
        details={"agent_id": agent_id, "credential_count": len(credentials)},
    )
    db.commit()
    return LifecycleActionResult(
        status="disabled",
        agent_id=agent_id,
        agent_disabled=True,
    )


def delete_agent(
    db: Session,
    agent_id: str,
    *,
    actor_id: str | None = None,
) -> LifecycleActionResult | None:
    status = _find_agent_status(db, agent_id)
    credentials = list(
        db.scalars(select(AgentCredential).where(AgentCredential.agent_id == agent_id))
    )
    asset = _find_asset_by_agent_id(db, agent_id)
    if status is None and not credentials and asset is None:
        return None

    stats = _delete_asset_model(db, asset) if asset is not None else _AssetDeleteStats()
    credentials_deleted = _execute_delete(
        db,
        delete(AgentCredential).where(AgentCredential.agent_id == agent_id),
    )
    auth_events_deleted = _execute_delete(
        db,
        delete(AgentAuthEvent).where(AgentAuthEvent.agent_id == agent_id),
    )
    status_deleted = _execute_delete(
        db,
        delete(AgentStatus).where(AgentStatus.agent_id == agent_id),
    )

    create_audit_log(
        db,
        action="agent.deleted",
        resource_type="agent",
        resource_id=agent_id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        summary=f"Deleted Agent {agent_id} and its asset data.",
        details={
            "agent_id": agent_id,
            "asset_id": stats.asset_id,
            "credentials_deleted": credentials_deleted,
            "auth_events_deleted": auth_events_deleted,
            "status_deleted": status_deleted,
            "match_results_deleted": stats.match_results_deleted,
            "verification_tasks_deleted": stats.verification_tasks_deleted,
        },
    )
    db.commit()
    return LifecycleActionResult(
        status="deleted",
        agent_id=agent_id,
        asset_id=stats.asset_id,
        asset_deleted=stats.asset_id is not None,
        agent_deleted=True,
        match_results_deleted=stats.match_results_deleted,
        verification_tasks_deleted=stats.verification_tasks_deleted,
    )


def delete_asset(
    db: Session,
    asset_id: str,
    *,
    delete_agent: bool = False,
    actor_id: str | None = None,
) -> LifecycleActionResult | None:
    asset = _find_asset(db, asset_id)
    if asset is None:
        return None
    agent_id = asset.agent_id
    stats = _delete_asset_model(db, asset)
    agent_deleted = False
    if delete_agent and agent_id:
        _execute_delete(db, delete(AgentCredential).where(AgentCredential.agent_id == agent_id))
        _execute_delete(db, delete(AgentAuthEvent).where(AgentAuthEvent.agent_id == agent_id))
        _execute_delete(db, delete(AgentStatus).where(AgentStatus.agent_id == agent_id))
        agent_deleted = True

    create_audit_log(
        db,
        action="asset.deleted",
        resource_type="asset",
        resource_id=stats.asset_id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        summary=(
            f"Deleted asset {stats.asset_id}"
            + (f" and Agent {agent_id}." if agent_deleted else ".")
        ),
        details={
            "asset_id": stats.asset_id,
            "agent_id": agent_id,
            "agent_deleted": agent_deleted,
            "match_results_deleted": stats.match_results_deleted,
            "verification_tasks_deleted": stats.verification_tasks_deleted,
        },
    )
    db.commit()
    return LifecycleActionResult(
        status="deleted",
        agent_id=agent_id,
        asset_id=stats.asset_id,
        asset_deleted=True,
        agent_deleted=agent_deleted,
        match_results_deleted=stats.match_results_deleted,
        verification_tasks_deleted=stats.verification_tasks_deleted,
    )


@dataclass(frozen=True)
class _AssetDeleteStats:
    asset_id: str | None = None
    match_results_deleted: int = 0
    verification_tasks_deleted: int = 0


def _delete_asset_model(db: Session, asset: Asset | None) -> _AssetDeleteStats:
    if asset is None:
        return _AssetDeleteStats()

    asset_id = asset.id
    match_result_ids = set(
        db.scalars(select(MatchResult.id).where(MatchResult.asset_id == asset_id)).all()
    )
    task_conditions = [VerificationTask.asset_id == asset_id]
    if match_result_ids:
        task_conditions.append(VerificationTask.match_result_id.in_(match_result_ids))
    verification_task_ids = set(
        db.scalars(
            select(VerificationTask.id).where(or_(*task_conditions))
        ).all()
    )

    if match_result_ids:
        db.execute(
            delete(VerificationEvidence).where(
                VerificationEvidence.match_result_id.in_(match_result_ids)
            )
        )
        db.execute(
            delete(MatchEvidence).where(MatchEvidence.match_result_id.in_(match_result_ids))
        )
        db.execute(
            delete(MatchResultHandlingRecord).where(
                MatchResultHandlingRecord.match_result_id.in_(match_result_ids)
            )
        )
    if verification_task_ids:
        db.execute(
            update(VerificationTask)
            .where(VerificationTask.id.in_(verification_task_ids))
            .values(previous_task_id=None)
        )
        db.execute(delete(VerificationTask).where(VerificationTask.id.in_(verification_task_ids)))
    if match_result_ids:
        db.execute(delete(MatchResult).where(MatchResult.id.in_(match_result_ids)))

    firewall_ids = set(
        db.scalars(select(AssetFirewall.id).where(AssetFirewall.asset_id == asset_id)).all()
    )
    if firewall_ids:
        from app.db.models import AssetFirewallRule

        db.execute(
            delete(AssetFirewallRule).where(AssetFirewallRule.firewall_id.in_(firewall_ids))
        )
    db.execute(delete(AssetFirewall).where(AssetFirewall.asset_id == asset_id))
    db.execute(delete(AssetSnapshot).where(AssetSnapshot.asset_id == asset_id))
    db.execute(delete(AssetComponent).where(AssetComponent.asset_id == asset_id))
    db.execute(delete(AssetExposure).where(AssetExposure.asset_id == asset_id))
    db.execute(delete(Asset).where(Asset.id == asset_id))
    db.flush()
    return _AssetDeleteStats(
        asset_id=asset_id,
        match_results_deleted=len(match_result_ids),
        verification_tasks_deleted=len(verification_task_ids),
    )


def _find_agent_status(db: Session, agent_id: str) -> AgentStatus | None:
    return db.scalar(select(AgentStatus).where(AgentStatus.agent_id == agent_id))


def _find_asset_by_agent_id(db: Session, agent_id: str) -> Asset | None:
    return db.scalar(select(Asset).where(Asset.agent_id == agent_id))


def _find_asset(db: Session, asset_id: str) -> Asset | None:
    return db.scalar(
        select(Asset).where(or_(Asset.id == asset_id, Asset.agent_id == asset_id))
    )


def _execute_delete(db: Session, statement) -> int:
    result = db.execute(statement)
    return int(result.rowcount or 0)
