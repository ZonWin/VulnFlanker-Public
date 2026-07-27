from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.base import utcnow
from app.db.models import IntelCollectionRun, WatchVulnMonitorConfig
from app.schemas.intel import WatchVulnMonitorConfigOut, WatchVulnMonitorConfigUpdate


WATCHVULN_MONITOR_CONFIG_ID = "default"
WATCHVULN_MONITOR_MIN_INTERVAL_SECONDS = 60
WATCHVULN_MONITOR_MAX_LIMIT = 5000


def get_watchvuln_monitor_config(
    db: Session,
    *,
    settings: Settings | None = None,
) -> WatchVulnMonitorConfig:
    config = db.get(WatchVulnMonitorConfig, WATCHVULN_MONITOR_CONFIG_ID)
    if config is not None:
        return config

    settings = settings or get_settings()
    interval_seconds = max(
        WATCHVULN_MONITOR_MIN_INTERVAL_SECONDS,
        int(settings.watchvuln_monitor_interval_seconds),
    )
    limit = _normalize_limit(settings.watchvuln_monitor_limit)
    config = WatchVulnMonitorConfig(
        id=WATCHVULN_MONITOR_CONFIG_ID,
        enabled=settings.watchvuln_monitor_enabled,
        interval_seconds=interval_seconds,
        limit=limit,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def get_watchvuln_monitor_status(
    db: Session,
    *,
    settings: Settings | None = None,
) -> WatchVulnMonitorConfigOut:
    config = get_watchvuln_monitor_config(db, settings=settings)
    latest_run = _latest_scheduled_run(db)
    return _to_monitor_config_out(config, latest_run)


def update_watchvuln_monitor_config(
    db: Session,
    update: WatchVulnMonitorConfigUpdate,
) -> WatchVulnMonitorConfigOut:
    config = get_watchvuln_monitor_config(db)
    fields = update.model_fields_set

    if "enabled" in fields and update.enabled is not None:
        config.enabled = update.enabled
    if "interval_seconds" in fields and update.interval_seconds is not None:
        config.interval_seconds = update.interval_seconds
    if "limit" in fields:
        config.limit = update.limit

    db.add(config)
    db.commit()
    db.refresh(config)
    latest_run = _latest_scheduled_run(db)
    return _to_monitor_config_out(config, latest_run)


def should_run_watchvuln_monitor(
    db: Session,
    *,
    config: WatchVulnMonitorConfig | None = None,
) -> bool:
    config = config or get_watchvuln_monitor_config(db)
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
            IntelCollectionRun.source_name == "watchvuln",
            IntelCollectionRun.trigger_type == "scheduled",
        )
        .order_by(desc(IntelCollectionRun.started_at))
    )


def _to_monitor_config_out(
    config: WatchVulnMonitorConfig,
    latest_run: IntelCollectionRun | None,
) -> WatchVulnMonitorConfigOut:
    next_run_at = _next_run_at(config, latest_run)
    return WatchVulnMonitorConfigOut(
        enabled=config.enabled,
        interval_seconds=config.interval_seconds,
        limit=config.limit,
        last_run_id=latest_run.id if latest_run else None,
        last_status=latest_run.status if latest_run else None,
        last_started_at=latest_run.started_at if latest_run else None,
        last_finished_at=latest_run.finished_at if latest_run else None,
        last_error=latest_run.error_message if latest_run else None,
        next_run_at=next_run_at,
        updated_at=config.updated_at,
    )


def _next_run_at(
    config: WatchVulnMonitorConfig,
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
    return min(limit, WATCHVULN_MONITOR_MAX_LIMIT)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
