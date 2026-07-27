from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AIProfile(TimestampMixin, Base):
    __tablename__ = "ai_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(64))
    model_vendor: Mapped[str] = mapped_column(String(64), default="openai")
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_web_search: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_external_network: Mapped[bool] = mapped_column(Boolean, default=False)
    json_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    daily_call_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_token_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_user_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_output_contract: Mapped[str | None] = mapped_column(Text, nullable=True)

    call_logs: Mapped[list["AICallLog"]] = relationship(back_populates="profile")
    enrichments: Mapped[list["VulnerabilityAIEnrichment"]] = relationship(
        back_populates="profile"
    )
