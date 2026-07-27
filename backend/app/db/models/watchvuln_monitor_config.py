from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WatchVulnMonitorConfig(TimestampMixin, Base):
    __tablename__ = "watchvuln_monitor_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
