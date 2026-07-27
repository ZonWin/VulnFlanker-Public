from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


AutoAcceptPolicy = Literal["strict", "moderate", "relaxed"]


class PlatformSettingsUpdate(BaseModel):
    platform_name: str | None = Field(default=None, max_length=80)
    platform_subtitle: str | None = Field(default=None, max_length=120)
    logo_data_url: str | None = Field(default=None, max_length=600_000)
    ai_enabled: bool | None = None
    ai_auto_enrich_enabled: bool | None = None
    ai_auto_accept_enabled: bool | None = None
    ai_auto_accept_policy: AutoAcceptPolicy | None = None
    ai_auto_accept_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_web_auto_accept_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_layer2_daily_limit: int | None = Field(default=None, ge=1, le=10_000)
    ai_batch_max_size: int | None = Field(default=None, ge=1, le=500)
    ai_allow_web_enrichment_default: bool | None = None
    auto_match_on_new_asset: bool | None = None
    auto_match_on_new_vulnerability: bool | None = None


class PlatformSettingsOut(BaseModel):
    id: str = "default"
    platform_name: str
    platform_subtitle: str
    logo_data_url: str | None = None
    ai_enabled: bool = True
    ai_auto_enrich_enabled: bool = False
    ai_auto_accept_enabled: bool = False
    ai_auto_accept_policy: AutoAcceptPolicy = "moderate"
    ai_auto_accept_confidence: float = 0.85
    ai_web_auto_accept_confidence: float = 0.8
    ai_layer2_daily_limit: int = 50
    ai_batch_max_size: int = 100
    ai_allow_web_enrichment_default: bool = False
    auto_match_on_new_asset: bool = False
    auto_match_on_new_vulnerability: bool = False
    updated_at: datetime
