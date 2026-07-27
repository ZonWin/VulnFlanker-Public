from __future__ import annotations

from datetime import datetime, timezone

from app.db.base import utcnow
from app.db.models import MatchResult
from app.services.rule_numeric_config import RuleNumericConfigValues
from app.services.risk import RISK_MODEL_VERSION, RiskBreakdown, calculate_match_risk


def apply_risk_snapshot(
    match_result: MatchResult,
    *,
    numeric_config: RuleNumericConfigValues | None = None,
) -> RiskBreakdown:
    risk = build_risk_breakdown(match_result, numeric_config=numeric_config)
    match_result.risk_score = risk.score
    match_result.risk_priority = risk.priority
    match_result.risk_model_version = risk.model_version
    match_result.risk_factors_json = risk.factor_dicts()
    match_result.risk_explanation = risk.explanation
    return risk


def build_risk_breakdown(
    match_result: MatchResult,
    *,
    numeric_config: RuleNumericConfigValues | None = None,
) -> RiskBreakdown:
    asset = match_result.asset
    vulnerability = match_result.vulnerability
    return calculate_match_risk(
        status=match_result.status,
        severity_cvss=vulnerability.severity_cvss,
        kev_status=vulnerability.kev_status,
        poc_status=vulnerability.poc_status,
        wild_exploitation_status=vulnerability.wild_exploitation_status,
        epss=vulnerability.epss,
        exposure_type=asset.exposure_type,
        has_public_exposure=any(exposure.is_public for exposure in asset.exposures),
        asset_criticality=asset.criticality,
        confidence=match_result.confidence,
        verification_state=_verification_state(match_result),
        asset_snapshot_age_seconds=_asset_snapshot_age_seconds(match_result),
        config=numeric_config,
    )


def stored_or_current_risk_breakdown(match_result: MatchResult) -> RiskBreakdown:
    if (
        match_result.risk_model_version
        and match_result.risk_model_version != "risk-v1"
        and match_result.risk_factors_json
    ):
        return RiskBreakdown(
            score=match_result.risk_score,
            priority=match_result.risk_priority or "none",
            factors=tuple(),
            explanation=match_result.risk_explanation or "",
            model_version=match_result.risk_model_version,
        )
    return build_risk_breakdown(match_result)


def _verification_state(match_result: MatchResult) -> str:
    if match_result.status == "verified":
        return "verified"

    task_statuses = {task.status for task in match_result.verification_tasks}
    if task_statuses & {"queued", "in_progress", "cancel_requested"}:
        return "verification_pending"
    if task_statuses & {"failed", "rejected", "cancelled"}:
        return "verification_failed"
    if match_result.status in {"affected", "needs_review"}:
        return match_result.status
    return "unverified"


def _asset_snapshot_age_seconds(match_result: MatchResult) -> int | None:
    last_seen_at = match_result.asset.last_seen_at
    if last_seen_at is None:
        return None
    return max(0, int((utcnow() - _ensure_aware(last_seen_at)).total_seconds()))


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def risk_snapshot_defaults() -> dict[str, object]:
    return {
        "risk_model_version": RISK_MODEL_VERSION,
        "risk_factors_json": [],
        "risk_explanation": None,
        "risk_priority": "none",
    }
