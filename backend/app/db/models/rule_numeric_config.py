from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class RuleNumericConfig(TimestampMixin, Base):
    __tablename__ = "rule_numeric_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")
    model_version: Mapped[str] = mapped_column(String(32), default="risk-v2.0")
    matching_confidences_json: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_factor_values_json: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_priority_thresholds_json: Mapped[dict] = mapped_column(JSON, default=dict)
