from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PlatformSettings(TimestampMixin, Base):
    __tablename__ = "platform_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")
    platform_name: Mapped[str] = mapped_column(String(80), default="VulnFlanker")
    platform_subtitle: Mapped[str] = mapped_column(String(120), default="漏洞监测平台")
    logo_data_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_auto_enrich_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_auto_accept_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_auto_accept_policy: Mapped[str] = mapped_column(String(32), default="moderate")
    ai_auto_accept_confidence: Mapped[float] = mapped_column(Float, default=0.85)
    ai_web_auto_accept_confidence: Mapped[float] = mapped_column(Float, default=0.8)
    ai_layer2_daily_limit: Mapped[int] = mapped_column(Integer, default=50)
    ai_batch_max_size: Mapped[int] = mapped_column(Integer, default=100)
    ai_allow_web_enrichment_default: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_match_on_new_asset: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_match_on_new_vulnerability: Mapped[bool] = mapped_column(Boolean, default=False)
