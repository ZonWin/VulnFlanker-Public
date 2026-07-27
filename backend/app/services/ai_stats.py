from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import AICallLog, AIProfile, VulnerabilityAIEnrichment
from app.schemas.ai import AIEnrichmentProfileStats, AIEnrichmentStatsOut
from app.services.vulnerability_ai_quality_gate import evaluate_ai_enrichment_quality


ENRICHMENT_TASK_TYPES = (
    "vulnerability_enrichment_layer1",
    "vulnerability_enrichment_layer2",
)


def get_ai_enrichment_stats(db: Session) -> AIEnrichmentStatsOut:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_call_count = db.scalar(
        select(func.count(AICallLog.id)).where(
            AICallLog.created_at >= today,
            AICallLog.task_type.in_(ENRICHMENT_TASK_TYPES),
        )
    ) or 0
    today_token_count = db.scalar(
        select(func.coalesce(func.sum(AICallLog.total_tokens), 0)).where(
            AICallLog.created_at >= today,
            AICallLog.task_type.in_(ENRICHMENT_TASK_TYPES),
        )
    ) or 0

    status_counts = dict(
        db.execute(
            select(
                VulnerabilityAIEnrichment.status,
                func.count(VulnerabilityAIEnrichment.id),
            ).group_by(VulnerabilityAIEnrichment.status)
        ).all()
    )
    average_confidence = db.scalar(
        select(func.avg(VulnerabilityAIEnrichment.confidence)).where(
            VulnerabilityAIEnrichment.confidence.is_not(None)
        )
    )
    quality_gate_distribution: dict[str, int] = {}
    quality_gate_reason_distribution: dict[str, int] = {}
    for enrichment in db.scalars(select(VulnerabilityAIEnrichment)).all():
        gate = evaluate_ai_enrichment_quality(db, enrichment)
        quality_gate_distribution[gate.quality_gate_status] = (
            quality_gate_distribution.get(gate.quality_gate_status, 0) + 1
        )
        for reason in gate.quality_gate_reasons:
            quality_gate_reason_distribution[reason] = (
                quality_gate_reason_distribution.get(reason, 0) + 1
            )

    return AIEnrichmentStatsOut(
        today_call_count=int(today_call_count),
        today_token_count=int(today_token_count),
        layer1_success_rate=_layer_success_rate(db, "vulnerability_enrichment_layer1", today),
        layer2_success_rate=_layer_success_rate(db, "vulnerability_enrichment_layer2", today),
        pending_review_count=int(status_counts.get("pending_review", 0)),
        accepted_count=int(status_counts.get("accepted", 0)),
        rejected_count=int(status_counts.get("rejected", 0)),
        auto_accepted_count=int(status_counts.get("auto_accepted", 0)),
        failed_count=int(status_counts.get("failed", 0)),
        insufficient_count=int(status_counts.get("insufficient", 0)),
        average_confidence=float(average_confidence) if average_confidence is not None else None,
        quality_gate_distribution=dict(sorted(quality_gate_distribution.items())),
        quality_gate_reason_distribution=dict(sorted(quality_gate_reason_distribution.items())),
        by_profile=_profile_stats(db, today),
    )


def _layer_success_rate(db: Session, task_type: str, since: datetime) -> float | None:
    rows = db.execute(
        select(AICallLog.status, func.count(AICallLog.id))
        .where(AICallLog.task_type == task_type, AICallLog.created_at >= since)
        .group_by(AICallLog.status)
    ).all()
    counts = {status: int(count) for status, count in rows}
    total = sum(counts.values())
    if not total:
        return None
    return counts.get("success", 0) / total


def _profile_stats(db: Session, since: datetime) -> list[AIEnrichmentProfileStats]:
    rows = db.execute(
        select(
            AICallLog.profile_id,
            AIProfile.profile_key,
            AICallLog.model,
            func.count(AICallLog.id),
            func.coalesce(func.sum(AICallLog.total_tokens), 0),
            func.sum(case((AICallLog.status == "failed", 1), else_=0)),
        )
        .outerjoin(AIProfile, AIProfile.id == AICallLog.profile_id)
        .where(
            AICallLog.created_at >= since,
            AICallLog.task_type.in_(ENRICHMENT_TASK_TYPES),
        )
        .group_by(AICallLog.profile_id, AIProfile.profile_key, AICallLog.model)
    ).all()
    return [
        AIEnrichmentProfileStats(
            profile_id=profile_id,
            profile_key=profile_key,
            model=model,
            call_count=int(call_count or 0),
            token_count=int(token_count or 0),
            failed_count=int(failed_count or 0),
        )
        for profile_id, profile_key, model, call_count, token_count, failed_count in rows
    ]
