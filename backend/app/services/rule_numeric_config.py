from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import RuleNumericConfig
from app.schemas.rule_numeric_config import RuleNumericConfigOut, RuleNumericConfigUpdate
from app.services.audit import create_audit_log


RULE_NUMERIC_CONFIG_ID = "default"
RISK_MODEL_VERSION = "risk-v2.0"

DEFAULT_MATCHING_CONFIDENCES: dict[str, dict[str, float]] = {
    "product_rule": {
        "missing_product": 0.20,
        "no_candidate": 0.82,
        "matched": 0.78,
    },
    "version_rule": {
        "no_observed_version": 0.35,
        "exact_affected": 0.78,
        "no_machine_readable_range": 0.45,
        "affected_range": 0.82,
        "uncertain_comparison": 0.50,
        "safe_range": 0.86,
    },
    "os_rule": {
        "not_applicable": 0.00,
        "matched": 0.72,
        "not_matched": 0.84,
    },
    "feature_rule": {
        "not_applicable": 0.00,
        "matched": 0.62,
        "missing_observed": 0.42,
    },
    "exposure_rule": {
        "not_applicable": 0.00,
        "local_listening": 0.55,
        "no_public_exposure": 0.80,
        "public_exposure": 0.76,
    },
    "pipeline": {
        "no_conclusive_result": 0.30,
    },
}

DEFAULT_RISK_FACTOR_VALUES: dict[str, dict[str, float]] = {
    "exploitability": {
        "kev": 8.0,
        "poc": 6.5,
        "wild_exploitation": 9.0,
        "epss_multiplier": 10.0,
        "default": 0.0,
    },
    "exposure": {
        "public_exposure": 10.0,
        "internet": 8.0,
        "public": 8.0,
        "external": 8.0,
        "dmz": 6.0,
        "default": 0.0,
    },
    "business_criticality": {
        "low": 2.0,
        "medium": 5.0,
        "high": 8.0,
        "critical": 10.0,
        "default": 5.0,
    },
    "verification": {
        "verified": 10.0,
        "verification_pending": 5.0,
        "verification_failed": 3.0,
        "affected": 2.0,
        "needs_review": 1.0,
        "unverified": 1.0,
        "default": 1.0,
    },
    "asset_freshness": {
        "fresh": 10.0,
        "stale": 6.0,
        "critical": 2.0,
        "unknown": 0.0,
    },
}

DEFAULT_RISK_WEIGHTS = {
    "severity": 0.30,
    "exploitability": 0.18,
    "exposure": 0.15,
    "business_criticality": 0.17,
    "confidence": 0.08,
    "verification": 0.07,
    "asset_freshness": 0.05,
}

DEFAULT_RISK_PRIORITY_THRESHOLDS = {
    "critical": 8.5,
    "high": 7.0,
    "medium": 4.0,
    "low": 0.01,
}


@dataclass(frozen=True)
class RuleNumericConfigValues:
    model_version: str
    matching_confidences: dict[str, dict[str, float]]
    risk_factor_values: dict[str, dict[str, float]]
    risk_weights: dict[str, float]
    risk_priority_thresholds: dict[str, float]

    @property
    def weight_total(self) -> float:
        return round(sum(self.risk_weights.values()), 4)

    @property
    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if abs(self.weight_total - 1.0) > 0.001:
            warnings.append(f"Risk weights total {self.weight_total:.4f}; expected 1.0000.")
        return warnings


def get_rule_numeric_config(db: Session) -> RuleNumericConfig:
    config = db.get(RuleNumericConfig, RULE_NUMERIC_CONFIG_ID)
    if config is not None:
        return config

    config = RuleNumericConfig(
        id=RULE_NUMERIC_CONFIG_ID,
        model_version=RISK_MODEL_VERSION,
        matching_confidences_json=deepcopy(DEFAULT_MATCHING_CONFIDENCES),
        risk_factor_values_json=deepcopy(DEFAULT_RISK_FACTOR_VALUES),
        risk_weights_json=deepcopy(DEFAULT_RISK_WEIGHTS),
        risk_priority_thresholds_json=deepcopy(DEFAULT_RISK_PRIORITY_THRESHOLDS),
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def get_rule_numeric_config_values(db: Session) -> RuleNumericConfigValues:
    return _values_from_model(get_rule_numeric_config(db))


def get_rule_numeric_config_out(db: Session) -> RuleNumericConfigOut:
    config = get_rule_numeric_config(db)
    values = _values_from_model(config)
    return _to_out(config, values)


def update_rule_numeric_config(
    db: Session,
    update: RuleNumericConfigUpdate,
    *,
    actor_id: str | None = None,
    actor_details: dict[str, object | None] | None = None,
) -> RuleNumericConfigOut:
    config = get_rule_numeric_config(db)
    before = _values_from_model(config)
    fields = update.model_fields_set

    matching_confidences = deepcopy(before.matching_confidences)
    risk_factor_values = deepcopy(before.risk_factor_values)
    risk_weights = deepcopy(before.risk_weights)
    risk_priority_thresholds = deepcopy(before.risk_priority_thresholds)

    if "matching_confidences" in fields and update.matching_confidences is not None:
        matching_confidences = _deep_merge(matching_confidences, update.matching_confidences)
    if "risk_factor_values" in fields and update.risk_factor_values is not None:
        risk_factor_values = _deep_merge(risk_factor_values, update.risk_factor_values)
    if "risk_weights" in fields and update.risk_weights is not None:
        risk_weights = {**risk_weights, **update.risk_weights}
    if (
        "risk_priority_thresholds" in fields
        and update.risk_priority_thresholds is not None
    ):
        risk_priority_thresholds = {
            **risk_priority_thresholds,
            **update.risk_priority_thresholds,
        }

    values = RuleNumericConfigValues(
        model_version=RISK_MODEL_VERSION,
        matching_confidences=_validate_nested_map(
            matching_confidences,
            DEFAULT_MATCHING_CONFIDENCES,
            minimum=0.0,
            maximum=1.0,
            label="matching_confidences",
        ),
        risk_factor_values=_validate_nested_map(
            risk_factor_values,
            DEFAULT_RISK_FACTOR_VALUES,
            minimum=0.0,
            maximum=10.0,
            label="risk_factor_values",
        ),
        risk_weights=_validate_flat_map(
            risk_weights,
            DEFAULT_RISK_WEIGHTS,
            minimum=0.0,
            maximum=1.0,
            label="risk_weights",
        ),
        risk_priority_thresholds=_validate_priority_thresholds(
            risk_priority_thresholds
        ),
    )

    _apply_values(config, values)
    db.add(config)
    create_audit_log(
        db,
        action="rule_numeric_config.updated",
        resource_type="rule_numeric_config",
        resource_id=config.id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        outcome="success",
        summary="Updated matching confidence and risk numeric configuration.",
        details={
            **(actor_details or {}),
            "updated_fields": sorted(fields),
            "weight_total": values.weight_total,
            "warnings": values.warnings,
        },
    )
    db.commit()
    db.refresh(config)
    return _to_out(config, _values_from_model(config))


def reset_rule_numeric_config(
    db: Session,
    *,
    actor_id: str | None = None,
    actor_details: dict[str, object | None] | None = None,
) -> RuleNumericConfigOut:
    config = get_rule_numeric_config(db)
    values = default_rule_numeric_config_values()
    _apply_values(config, values)
    db.add(config)
    create_audit_log(
        db,
        action="rule_numeric_config.reset",
        resource_type="rule_numeric_config",
        resource_id=config.id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        outcome="success",
        summary="Reset matching confidence and risk numeric configuration to defaults.",
        details=actor_details or {},
    )
    db.commit()
    db.refresh(config)
    return _to_out(config, _values_from_model(config))


def default_rule_numeric_config_values() -> RuleNumericConfigValues:
    return RuleNumericConfigValues(
        model_version=RISK_MODEL_VERSION,
        matching_confidences=deepcopy(DEFAULT_MATCHING_CONFIDENCES),
        risk_factor_values=deepcopy(DEFAULT_RISK_FACTOR_VALUES),
        risk_weights=deepcopy(DEFAULT_RISK_WEIGHTS),
        risk_priority_thresholds=deepcopy(DEFAULT_RISK_PRIORITY_THRESHOLDS),
    )


def _values_from_model(config: RuleNumericConfig) -> RuleNumericConfigValues:
    return RuleNumericConfigValues(
        model_version=config.model_version or RISK_MODEL_VERSION,
        matching_confidences=_validate_nested_map(
            _deep_merge(
                deepcopy(DEFAULT_MATCHING_CONFIDENCES),
                config.matching_confidences_json or {},
            ),
            DEFAULT_MATCHING_CONFIDENCES,
            minimum=0.0,
            maximum=1.0,
            label="matching_confidences",
        ),
        risk_factor_values=_validate_nested_map(
            _deep_merge(
                deepcopy(DEFAULT_RISK_FACTOR_VALUES),
                config.risk_factor_values_json or {},
            ),
            DEFAULT_RISK_FACTOR_VALUES,
            minimum=0.0,
            maximum=10.0,
            label="risk_factor_values",
        ),
        risk_weights=_validate_flat_map(
            {**DEFAULT_RISK_WEIGHTS, **(config.risk_weights_json or {})},
            DEFAULT_RISK_WEIGHTS,
            minimum=0.0,
            maximum=1.0,
            label="risk_weights",
        ),
        risk_priority_thresholds=_validate_priority_thresholds(
            {
                **DEFAULT_RISK_PRIORITY_THRESHOLDS,
                **(config.risk_priority_thresholds_json or {}),
            }
        ),
    )


def _apply_values(
    config: RuleNumericConfig,
    values: RuleNumericConfigValues,
) -> None:
    config.model_version = values.model_version
    config.matching_confidences_json = deepcopy(values.matching_confidences)
    config.risk_factor_values_json = deepcopy(values.risk_factor_values)
    config.risk_weights_json = deepcopy(values.risk_weights)
    config.risk_priority_thresholds_json = deepcopy(values.risk_priority_thresholds)


def _to_out(
    config: RuleNumericConfig,
    values: RuleNumericConfigValues,
) -> RuleNumericConfigOut:
    return RuleNumericConfigOut(
        id=config.id,
        model_version=values.model_version,
        matching_confidences=values.matching_confidences,
        risk_factor_values=values.risk_factor_values,
        risk_weights=values.risk_weights,
        risk_priority_thresholds=values.risk_priority_thresholds,
        weight_total=values.weight_total,
        warnings=values.warnings,
        updated_at=config.updated_at,
    )


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_nested_map(
    value: dict[str, Any],
    defaults: dict[str, dict[str, float]],
    *,
    minimum: float,
    maximum: float,
    label: str,
) -> dict[str, dict[str, float]]:
    validated: dict[str, dict[str, float]] = {}
    for group, default_items in defaults.items():
        raw_items = value.get(group, {})
        if not isinstance(raw_items, dict):
            raise ValueError(f"{label}.{group} must be an object.")
        validated[group] = _validate_flat_map(
            {**default_items, **raw_items},
            default_items,
            minimum=minimum,
            maximum=maximum,
            label=f"{label}.{group}",
        )
    return validated


def _validate_flat_map(
    value: dict[str, Any],
    defaults: dict[str, float],
    *,
    minimum: float,
    maximum: float,
    label: str,
) -> dict[str, float]:
    validated: dict[str, float] = {}
    for key, default in defaults.items():
        raw_value = value.get(key, default)
        try:
            number = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label}.{key} must be numeric.") from exc
        if number < minimum or number > maximum:
            raise ValueError(
                f"{label}.{key} must be between {minimum:g} and {maximum:g}."
            )
        validated[key] = round(number, 4)
    return validated


def _validate_priority_thresholds(value: dict[str, Any]) -> dict[str, float]:
    thresholds = _validate_flat_map(
        value,
        DEFAULT_RISK_PRIORITY_THRESHOLDS,
        minimum=0.0,
        maximum=10.0,
        label="risk_priority_thresholds",
    )
    if not (
        thresholds["low"]
        < thresholds["medium"]
        < thresholds["high"]
        < thresholds["critical"]
    ):
        raise ValueError(
            "risk_priority_thresholds must satisfy low < medium < high < critical."
        )
    return thresholds
