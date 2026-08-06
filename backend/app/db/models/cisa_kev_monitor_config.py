from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CisaKevMonitorConfig(TimestampMixin, Base):
    __tablename__ = "cisa_kev_monitor_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=86_400)
    limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_only: Mapped[bool] = mapped_column(Boolean, default=False)
