from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


NestedNumericMap = dict[str, dict[str, float]]


class RuleNumericConfigUpdate(BaseModel):
    matching_confidences: NestedNumericMap | None = None
    risk_factor_values: NestedNumericMap | None = None
    risk_weights: dict[str, float] | None = None
    risk_priority_thresholds: dict[str, float] | None = None


class RuleNumericConfigOut(BaseModel):
    id: str = "default"
    model_version: str
    matching_confidences: NestedNumericMap
    risk_factor_values: NestedNumericMap
    risk_weights: dict[str, float]
    risk_priority_thresholds: dict[str, float]
    weight_total: float
    warnings: list[str] = Field(default_factory=list)
    updated_at: datetime
