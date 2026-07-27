from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.services.rule_numeric_config import (
    DEFAULT_RISK_FACTOR_VALUES,
    DEFAULT_RISK_PRIORITY_THRESHOLDS,
    DEFAULT_RISK_WEIGHTS,
    RISK_MODEL_VERSION,
    RuleNumericConfigValues,
    default_rule_numeric_config_values,
)


ASSET_FRESHNESS_STALE_AFTER_SECONDS = 86_400
ASSET_FRESHNESS_CRITICAL_AFTER_SECONDS = 7 * 86_400
RISK_WEIGHTS = DEFAULT_RISK_WEIGHTS
RISK_PRIORITY_THRESHOLDS = DEFAULT_RISK_PRIORITY_THRESHOLDS


@dataclass(frozen=True)
class RiskWeights:
    severity: float = RISK_WEIGHTS["severity"]
    exploitability: float = RISK_WEIGHTS["exploitability"]
    exposure: float = RISK_WEIGHTS["exposure"]
    business_criticality: float = RISK_WEIGHTS["business_criticality"]
    confidence: float = RISK_WEIGHTS["confidence"]
    verification: float = RISK_WEIGHTS["verification"]
    asset_freshness: float = RISK_WEIGHTS["asset_freshness"]

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, float]) -> "RiskWeights":
        return cls(
            severity=float(mapping.get("severity", RISK_WEIGHTS["severity"])),
            exploitability=float(
                mapping.get("exploitability", RISK_WEIGHTS["exploitability"])
            ),
            exposure=float(mapping.get("exposure", RISK_WEIGHTS["exposure"])),
            business_criticality=float(
                mapping.get(
                    "business_criticality",
                    RISK_WEIGHTS["business_criticality"],
                )
            ),
            confidence=float(mapping.get("confidence", RISK_WEIGHTS["confidence"])),
            verification=float(mapping.get("verification", RISK_WEIGHTS["verification"])),
            asset_freshness=float(
                mapping.get("asset_freshness", RISK_WEIGHTS["asset_freshness"])
            ),
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "severity": self.severity,
            "exploitability": self.exploitability,
            "exposure": self.exposure,
            "business_criticality": self.business_criticality,
            "confidence": self.confidence,
            "verification": self.verification,
            "asset_freshness": self.asset_freshness,
        }

    def for_factor(self, name: str) -> float:
        return self.as_dict()[name]


def current_risk_weights() -> RiskWeights:
    return RiskWeights.from_mapping(default_rule_numeric_config_values().risk_weights)


def current_risk_config(
    config: RuleNumericConfigValues | None = None,
) -> dict[str, object]:
    active_config = config or default_rule_numeric_config_values()
    weights = RiskWeights.from_mapping(active_config.risk_weights)
    return {
        "model_version": active_config.model_version,
        "weights": weights.as_dict(),
        "priority_thresholds": active_config.risk_priority_thresholds,
        "weight_total": round(sum(weights.as_dict().values()), 4),
        "warnings": risk_config_warnings(weights),
    }


def risk_config_warnings(weights: RiskWeights | None = None) -> list[str]:
    active_weights = weights or current_risk_weights()
    total = sum(active_weights.as_dict().values())
    warnings = []
    if abs(total - 1.0) > 0.001:
        warnings.append(f"Risk weights total {total:.4f}; expected 1.0000.")
    for name, value in active_weights.as_dict().items():
        if value < 0:
            warnings.append(f"Risk weight {name} is negative.")
    return warnings


@dataclass(frozen=True)
class RiskFactor:
    name: str
    label: str
    value: float
    weight: float
    weighted_score: float
    evidence: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "value": self.value,
            "weight": self.weight,
            "weighted_score": self.weighted_score,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class RiskBreakdown:
    score: float
    priority: str
    factors: tuple[RiskFactor, ...]
    explanation: str
    model_version: str = RISK_MODEL_VERSION

    def factor_dicts(self) -> list[dict[str, object]]:
        return [factor.as_dict() for factor in self.factors]


def calculate_risk_score(
    severity_cvss: float | None,
    exploit_signal: float = 0.0,
    exposure_signal: float = 0.0,
    criticality_signal: float = 0.0,
    confidence_signal: float = 0.0,
    weights: RiskWeights | None = None,
) -> float:
    active_weights = weights or current_risk_weights()
    base = severity_cvss or 0.0
    score = (
        base * active_weights.severity
        + exploit_signal * active_weights.exploitability
        + exposure_signal * active_weights.exposure
        + criticality_signal * active_weights.business_criticality
        + confidence_signal * active_weights.confidence
    )
    return round(min(score, 10.0), 2)


def calculate_match_risk(
    *,
    status: str,
    severity_cvss: float | None,
    kev_status: bool = False,
    poc_status: bool = False,
    wild_exploitation_status: bool = False,
    epss: float | None = None,
    exposure_type: str | None = None,
    has_public_exposure: bool = False,
    asset_criticality: str | None = None,
    confidence: float = 0.0,
    verification_state: str | None = None,
    asset_snapshot_age_seconds: int | None = None,
    weights: RiskWeights | None = None,
    config: RuleNumericConfigValues | None = None,
) -> RiskBreakdown:
    active_config = config or default_rule_numeric_config_values()
    active_weights = weights or RiskWeights.from_mapping(active_config.risk_weights)
    factor_values = active_config.risk_factor_values
    if status == "not_affected":
        factors = _suppressed_factors(active_weights)
        return RiskBreakdown(
            score=0.0,
            priority="none",
            factors=factors,
            explanation="Risk score is 0.0 because the match status is not_affected.",
            model_version=active_config.model_version,
        )

    factors = (
        _severity_factor(severity_cvss, active_weights),
        _exploitability_factor(
            kev_status=kev_status,
            poc_status=poc_status,
            wild_exploitation_status=wild_exploitation_status,
            epss=epss,
            weights=active_weights,
            values=factor_values.get(
                "exploitability",
                DEFAULT_RISK_FACTOR_VALUES["exploitability"],
            ),
        ),
        _exposure_factor(
            exposure_type=exposure_type,
            has_public_exposure=has_public_exposure,
            weights=active_weights,
            values=factor_values.get("exposure", DEFAULT_RISK_FACTOR_VALUES["exposure"]),
        ),
        _criticality_factor(
            asset_criticality,
            active_weights,
            factor_values.get(
                "business_criticality",
                DEFAULT_RISK_FACTOR_VALUES["business_criticality"],
            ),
        ),
        _confidence_factor(confidence, active_weights),
        _verification_factor(
            verification_state or status,
            active_weights,
            factor_values.get(
                "verification",
                DEFAULT_RISK_FACTOR_VALUES["verification"],
            ),
        ),
        _asset_freshness_factor(
            asset_snapshot_age_seconds,
            active_weights,
            factor_values.get(
                "asset_freshness",
                DEFAULT_RISK_FACTOR_VALUES["asset_freshness"],
            ),
        ),
    )
    score = round(min(sum(factor.weighted_score for factor in factors), 10.0), 2)
    priority = risk_priority(score, thresholds=active_config.risk_priority_thresholds)
    return RiskBreakdown(
        score=score,
        priority=priority,
        factors=factors,
        explanation=_risk_explanation(
            score,
            priority,
            factors,
            model_version=active_config.model_version,
        ),
        model_version=active_config.model_version,
    )


def risk_priority(
    score: float,
    *,
    thresholds: Mapping[str, float] | None = None,
) -> str:
    active_thresholds = thresholds or RISK_PRIORITY_THRESHOLDS
    if score >= active_thresholds["critical"]:
        return "critical"
    if score >= active_thresholds["high"]:
        return "high"
    if score >= active_thresholds["medium"]:
        return "medium"
    if score >= active_thresholds["low"]:
        return "low"
    return "none"


def risk_priority_bounds(
    priority: str,
    *,
    thresholds: Mapping[str, float] | None = None,
) -> tuple[float, float | None]:
    normalized_priority = priority.lower()
    active_thresholds = thresholds or RISK_PRIORITY_THRESHOLDS
    if normalized_priority == "critical":
        return active_thresholds["critical"], None
    if normalized_priority == "high":
        return active_thresholds["high"], active_thresholds["critical"]
    if normalized_priority == "medium":
        return active_thresholds["medium"], active_thresholds["high"]
    if normalized_priority == "low":
        return active_thresholds["low"], active_thresholds["medium"]
    if normalized_priority == "none":
        return 0.0, active_thresholds["low"]
    raise ValueError(f"Unknown risk priority: {priority}")


def _suppressed_factors(weights: RiskWeights) -> tuple[RiskFactor, ...]:
    return tuple(
        _factor(
            name=name,
            label=label,
            value=0.0,
            evidence=("Match status is not_affected.",),
            weights=weights,
        )
        for name, label in (
            ("severity", "CVSS severity"),
            ("exploitability", "Exploitability signals"),
            ("exposure", "Exposure"),
            ("business_criticality", "Business criticality"),
            ("confidence", "Match confidence"),
            ("verification", "Verification status"),
            ("asset_freshness", "Asset freshness"),
        )
    )


def _severity_factor(severity_cvss: float | None, weights: RiskWeights) -> RiskFactor:
    value = _clamp(severity_cvss or 0.0)
    evidence = (f"CVSS {value:.1f}.",) if severity_cvss is not None else ("No CVSS signal.",)
    return _factor(
        name="severity",
        label="CVSS severity",
        value=value,
        evidence=evidence,
        weights=weights,
    )


def _exploitability_factor(
    *,
    kev_status: bool,
    poc_status: bool,
    wild_exploitation_status: bool,
    epss: float | None,
    weights: RiskWeights,
    values: Mapping[str, float],
) -> RiskFactor:
    value = 0.0
    evidence: list[str] = []
    if kev_status:
        value = max(value, _mapped_value(values, "kev", 8.0))
        evidence.append("Listed in CISA KEV.")
    if poc_status:
        value = max(value, _mapped_value(values, "poc", 6.5))
        evidence.append("Public PoC signal is present.")
    if wild_exploitation_status:
        value = max(value, _mapped_value(values, "wild_exploitation", 9.0))
        evidence.append("Wild exploitation signal is present.")
    if epss is not None:
        epss_signal = _clamp(epss * _mapped_value(values, "epss_multiplier", 10.0))
        value = max(value, epss_signal)
        evidence.append(f"EPSS signal {epss:.3f}.")
    if not evidence:
        evidence.append("No KEV, PoC, wild exploitation, or EPSS signal.")
    return _factor(
        name="exploitability",
        label="Exploitability signals",
        value=value,
        evidence=tuple(evidence),
        weights=weights,
    )


def _exposure_factor(
    *,
    exposure_type: str | None,
    has_public_exposure: bool,
    weights: RiskWeights,
    values: Mapping[str, float],
) -> RiskFactor:
    normalized_exposure = (exposure_type or "").lower()
    if has_public_exposure:
        return _factor(
            name="exposure",
            label="Exposure",
            value=_mapped_value(values, "public_exposure", 10.0),
            evidence=("Public-facing exposure is observed.",),
            weights=weights,
        )
    if normalized_exposure in {"internet", "public", "external"}:
        return _factor(
            name="exposure",
            label="Exposure",
            value=_mapped_value(values, normalized_exposure, 8.0),
            evidence=(f"Asset exposure_type is {exposure_type}.",),
            weights=weights,
        )
    if normalized_exposure == "dmz":
        return _factor(
            name="exposure",
            label="Exposure",
            value=_mapped_value(values, "dmz", 6.0),
            evidence=("Asset exposure_type is dmz.",),
            weights=weights,
        )
    return _factor(
        name="exposure",
        label="Exposure",
        value=_mapped_value(values, "default", 0.0),
        evidence=("No public exposure signal.",),
        weights=weights,
    )


def _criticality_factor(
    asset_criticality: str | None,
    weights: RiskWeights,
    values: Mapping[str, float],
) -> RiskFactor:
    normalized_criticality = (asset_criticality or "medium").lower()
    value = _mapped_value(
        values,
        normalized_criticality,
        _mapped_value(values, "default", 5.0),
    )
    return _factor(
        name="business_criticality",
        label="Business criticality",
        value=value,
        evidence=(f"Asset criticality is {normalized_criticality}.",),
        weights=weights,
    )


def _confidence_factor(confidence: float, weights: RiskWeights) -> RiskFactor:
    value = _clamp(confidence * 10)
    return _factor(
        name="confidence",
        label="Match confidence",
        value=value,
        evidence=(f"Match confidence is {confidence:.2f}.",),
        weights=weights,
    )


def _verification_factor(
    verification_state: str,
    weights: RiskWeights,
    values: Mapping[str, float],
) -> RiskFactor:
    normalized_state = (verification_state or "unverified").lower()
    evidence = {
        "verified": "Read-only verification evidence has confirmed this result.",
        "verification_pending": "A verification task is queued or in progress.",
        "verification_failed": "A verification task failed or was rejected.",
        "affected": "No verification evidence has confirmed this affected result yet.",
        "needs_review": "The match still needs review and has no conclusive verification.",
        "unverified": "No verification task has confirmed this result yet.",
    }
    return _factor(
        name="verification",
        label="Verification status",
        value=_mapped_value(
            values,
            normalized_state,
            _mapped_value(values, "default", 1.0),
        ),
        evidence=(evidence.get(normalized_state, evidence["unverified"]),),
        weights=weights,
    )


def _asset_freshness_factor(
    snapshot_age_seconds: int | None,
    weights: RiskWeights,
    values: Mapping[str, float],
) -> RiskFactor:
    if snapshot_age_seconds is None:
        return _factor(
            name="asset_freshness",
            label="Asset freshness",
            value=_mapped_value(values, "unknown", 0.0),
            evidence=("No asset snapshot timestamp is available.",),
            weights=weights,
        )
    if snapshot_age_seconds <= ASSET_FRESHNESS_STALE_AFTER_SECONDS:
        return _factor(
            name="asset_freshness",
            label="Asset freshness",
            value=_mapped_value(values, "fresh", 10.0),
            evidence=("Asset snapshot is fresh within 24 hours.",),
            weights=weights,
        )
    if snapshot_age_seconds <= ASSET_FRESHNESS_CRITICAL_AFTER_SECONDS:
        return _factor(
            name="asset_freshness",
            label="Asset freshness",
            value=_mapped_value(values, "stale", 6.0),
            evidence=("Asset snapshot is older than 24 hours but within 7 days.",),
            weights=weights,
        )
    return _factor(
        name="asset_freshness",
        label="Asset freshness",
        value=_mapped_value(values, "critical", 2.0),
        evidence=("Asset snapshot is older than 7 days.",),
        weights=weights,
    )


def _factor(
    *,
    name: str,
    label: str,
    value: float,
    evidence: tuple[str, ...],
    weights: RiskWeights,
) -> RiskFactor:
    weight = weights.for_factor(name)
    rounded_value = round(_clamp(value), 2)
    return RiskFactor(
        name=name,
        label=label,
        value=rounded_value,
        weight=weight,
        weighted_score=round(rounded_value * weight, 2),
        evidence=evidence,
    )


def _risk_explanation(
    score: float,
    priority: str,
    factors: tuple[RiskFactor, ...],
    *,
    model_version: str,
) -> str:
    if score == 0:
        return "No risk score was assigned."
    contributors = [
        factor
        for factor in sorted(factors, key=lambda item: item.weighted_score, reverse=True)
        if factor.weighted_score > 0
    ][:3]
    summary = ", ".join(
        f"{factor.name} {factor.value:.1f}" for factor in contributors
    )
    return (
        f"{priority} priority risk score {score:.2f} using {model_version}; "
        f"top factors: {summary}."
    )


def _mapped_value(values: Mapping[str, float], key: str, default: float) -> float:
    try:
        return float(values.get(key, default))
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    return max(0.0, min(float(value), 10.0))
