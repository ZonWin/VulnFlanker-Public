from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.base import utcnow
from app.db.models import CisaKevMonitorConfig, IntelCollectionRun
from app.schemas.intel import CisaKevMonitorConfigOut, CisaKevMonitorConfigUpdate


CISA_KEV_MONITOR_CONFIG_ID = "default"
CISA_KEV_MONITOR_MIN_INTERVAL_SECONDS = 300
CISA_KEV_MONITOR_MAX_LIMIT = 5000


def get_cisa_kev_monitor_config(
    db: Session,
    *,
    settings: Settings | None = None,
) -> CisaKevMonitorConfig:
    config = db.get(CisaKevMonitorConfig, CISA_KEV_MONITOR_CONFIG_ID)
    if config is not None:
        return config

    settings = settings or get_settings()
    config = CisaKevMonitorConfig(
        id=CISA_KEV_MONITOR_CONFIG_ID,
        enabled=settings.cisa_kev_monitor_enabled,
        interval_seconds=max(
            CISA_KEV_MONITOR_MIN_INTERVAL_SECONDS,
            int(settings.cisa_kev_monitor_interval_seconds),
        ),
        limit=_normalize_limit(settings.cisa_kev_monitor_limit),
        latest_only=False,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def get_cisa_kev_monitor_status(
    db: Session,
    *,
    settings: Settings | None = None,
) -> CisaKevMonitorConfigOut:
    config = get_cisa_kev_monitor_config(db, settings=settings)
    latest_run = _latest_scheduled_run(db)
    return _to_monitor_config_out(config, latest_run)


def update_cisa_kev_monitor_config(
    db: Session,
    update: CisaKevMonitorConfigUpdate,
) -> CisaKevMonitorConfigOut:
    config = get_cisa_kev_monitor_config(db)
    fields = update.model_fields_set

    if "enabled" in fields and update.enabled is not None:
        config.enabled = update.enabled
    if "interval_seconds" in fields and update.interval_seconds is not None:
        config.interval_seconds = update.interval_seconds
    if "limit" in fields:
        config.limit = update.limit
    if "latest_only" in fields and update.latest_only is not None:
        config.latest_only = update.latest_only

    db.add(config)
    db.commit()
    db.refresh(config)
    latest_run = _latest_scheduled_run(db)
    return _to_monitor_config_out(config, latest_run)


def should_run_cisa_kev_monitor(
    db: Session,
    *,
    config: CisaKevMonitorConfig | None = None,
) -> bool:
    config = config or get_cisa_kev_monitor_config(db)
    if not config.enabled:
        return False

    latest_run = _latest_scheduled_run(db)
    if latest_run is None:
        return True
    if latest_run.status in {"queued", "running"}:
        return False

    latest_started_at = _ensure_aware(latest_run.started_at)
    return utcnow() >= latest_started_at + timedelta(seconds=config.interval_seconds)


def _latest_scheduled_run(db: Session) -> IntelCollectionRun | None:
    return db.scalar(
        select(IntelCollectionRun)
        .where(
            IntelCollectionRun.source_name == "cisa-kev",
            IntelCollectionRun.trigger_type == "scheduled",
        )
        .order_by(desc(IntelCollectionRun.started_at))
    )


def _to_monitor_config_out(
    config: CisaKevMonitorConfig,
    latest_run: IntelCollectionRun | None,
) -> CisaKevMonitorConfigOut:
    next_run_at = _next_run_at(config, latest_run)
    return CisaKevMonitorConfigOut(
        enabled=config.enabled,
        interval_seconds=config.interval_seconds,
        limit=config.limit,
        latest_only=config.latest_only,
        last_run_id=latest_run.id if latest_run else None,
        last_status=latest_run.status if latest_run else None,
        last_started_at=latest_run.started_at if latest_run else None,
        last_finished_at=latest_run.finished_at if latest_run else None,
        last_error=latest_run.error_message if latest_run else None,
        next_run_at=next_run_at,
        updated_at=config.updated_at,
    )


def _next_run_at(
    config: CisaKevMonitorConfig,
    latest_run: IntelCollectionRun | None,
) -> datetime | None:
    if not config.enabled:
        return None
    if latest_run is None:
        return utcnow()
    started_at = _ensure_aware(latest_run.started_at)
    return started_at + timedelta(seconds=config.interval_seconds)


def _normalize_limit(limit: int | None) -> int | None:
    if limit is None or limit <= 0:
        return None
    return min(limit, CISA_KEV_MONITOR_MAX_LIMIT)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
