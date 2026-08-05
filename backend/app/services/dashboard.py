from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.models import (
    Asset,
    MatchResult,
    MatchResultHandlingRecord,
    Vulnerability,
)
from app.schemas.dashboard import (
    DashboardClosureSummary,
    DashboardDistributionItem,
    DashboardMetric,
    DashboardOverview,
    DashboardPeriod,
    DashboardTopRisk,
    DashboardTrendPoint,
)
from app.services.match_result_handling import (
    CLOSED_HANDLING_STATUSES,
    OPEN_HANDLING_STATUSES,
)
from app.services.match_results import RISK_QUEUE_STATUSES


RISK_PRIORITY_ORDER = ("critical", "high", "medium", "low", "none")
HANDLING_STATUS_ORDER = ("unprocessed", "notified", "remediating", "pending_review")


def get_dashboard_overview(
    db: Session,
    *,
    days: int = 7,
    start_date: date | None = None,
    end_date: date | None = None,
    now: datetime | None = None,
    timezone_name: str | None = None,
) -> DashboardOverview:
    tz_name = timezone_name or get_settings().system_timezone
    tz = ZoneInfo(tz_name)
    generated_at = _as_aware(now or utcnow()).astimezone(UTC)
    period = _build_period(
        tz,
        timezone_name=tz_name,
        generated_at=generated_at,
        days=days,
        start_date=start_date,
        end_date=end_date,
    )
    period_start = _local_day_start(period.start_date, tz)
    period_end = _local_day_start(period.end_date + timedelta(days=1), tz)
    previous_start = _local_day_start(period.previous_start_date, tz)
    previous_end = period_start

    current_risk_total = _count(
        db,
        MatchResult,
        MatchResult.status.in_(RISK_QUEUE_STATUSES),
        MatchResult.handling_status.in_(OPEN_HANDLING_STATUSES),
    )
    risk_period_new = _count(
        db,
        MatchResult,
        MatchResult.risk_entered_at >= period_start,
        MatchResult.risk_entered_at < period_end,
    )
    risk_previous_new = _count(
        db,
        MatchResult,
        MatchResult.risk_entered_at >= previous_start,
        MatchResult.risk_entered_at < previous_end,
    )
    asset_total = _count(db, Asset)
    asset_period_new = _count(
        db, Asset, Asset.created_at >= period_start, Asset.created_at < period_end
    )
    asset_previous_new = _count(
        db, Asset, Asset.created_at >= previous_start, Asset.created_at < previous_end
    )
    vulnerability_total = _count(db, Vulnerability)
    vulnerability_period_new = _count(
        db,
        Vulnerability,
        Vulnerability.created_at >= period_start,
        Vulnerability.created_at < period_end,
    )
    vulnerability_previous_new = _count(
        db,
        Vulnerability,
        Vulnerability.created_at >= previous_start,
        Vulnerability.created_at < previous_end,
    )

    closure_records = list(
        db.scalars(
            select(MatchResultHandlingRecord).where(
                MatchResultHandlingRecord.to_status.in_(CLOSED_HANDLING_STATUSES),
                MatchResultHandlingRecord.created_at >= period_start,
                MatchResultHandlingRecord.created_at < period_end,
            )
        ).all()
    )
    closure_counts = Counter(record.to_status for record in closure_records)

    return DashboardOverview(
        period=period,
        risk=_metric(current_risk_total, risk_period_new, risk_previous_new),
        asset=_metric(asset_total, asset_period_new, asset_previous_new),
        vulnerability=_metric(
            vulnerability_total,
            vulnerability_period_new,
            vulnerability_previous_new,
        ),
        closure=DashboardClosureSummary(
            total=sum(closure_counts.values()),
            resolved=closure_counts["resolved"],
            false_positive=closure_counts["false_positive"],
            risk_accepted=closure_counts["risk_accepted"],
        ),
        risk_priority_distribution=_current_distribution(
            db,
            MatchResult.risk_priority,
            RISK_PRIORITY_ORDER,
        ),
        handling_status_distribution=_current_distribution(
            db,
            MatchResult.handling_status,
            HANDLING_STATUS_ORDER,
        ),
        trend=_build_trend(
            db,
            start_date=period.start_date,
            end_date=period.end_date,
            period_start=period_start,
            period_end=period_end,
            timezone=tz,
            closure_records=closure_records,
        ),
        top_risks=_top_risks(db),
    )


def _build_period(
    timezone: ZoneInfo,
    *,
    timezone_name: str,
    generated_at: datetime,
    days: int,
    start_date: date | None,
    end_date: date | None,
) -> DashboardPeriod:
    if (start_date is None) != (end_date is None):
        raise ValueError("start_date and end_date must be provided together")
    if start_date is None or end_date is None:
        if days < 1 or days > 366:
            raise ValueError("days must be between 1 and 366")
        end_date = generated_at.astimezone(timezone).date()
        start_date = end_date - timedelta(days=days - 1)
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    period_days = (end_date - start_date).days + 1
    if period_days > 366:
        raise ValueError("dashboard period must not exceed 366 days")
    previous_end_date = start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=period_days - 1)
    return DashboardPeriod(
        timezone=timezone_name,
        start_date=start_date,
        end_date=end_date,
        previous_start_date=previous_start_date,
        previous_end_date=previous_end_date,
        generated_at=generated_at,
    )


def _count(db: Session, model, *conditions) -> int:
    statement = select(func.count()).select_from(model)
    if conditions:
        statement = statement.where(*conditions)
    return int(db.scalar(statement) or 0)


def _metric(current_total: int, period_new: int, previous_new: int) -> DashboardMetric:
    if previous_new == 0:
        change_percent = 0.0 if period_new == 0 else None
    else:
        change_percent = round((period_new - previous_new) / previous_new * 100, 1)
    return DashboardMetric(
        current_total=current_total,
        period_new=period_new,
        previous_new=previous_new,
        change_percent=change_percent,
    )


def _current_distribution(
    db: Session,
    column,
    order: tuple[str, ...],
) -> list[DashboardDistributionItem]:
    rows = db.execute(
        select(column, func.count(MatchResult.id))
        .where(
            MatchResult.status.in_(RISK_QUEUE_STATUSES),
            MatchResult.handling_status.in_(OPEN_HANDLING_STATUSES),
        )
        .group_by(column)
    ).all()
    counts = {str(key or "none"): int(count) for key, count in rows}
    return [
        DashboardDistributionItem(key=key, count=counts.get(key, 0))
        for key in order
    ]


def _build_trend(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    period_start: datetime,
    period_end: datetime,
    timezone: ZoneInfo,
    closure_records: list[MatchResultHandlingRecord],
) -> list[DashboardTrendPoint]:
    risk_entries = list(
        db.scalars(
            select(MatchResult.risk_entered_at).where(
                MatchResult.risk_entered_at >= period_start,
                MatchResult.risk_entered_at < period_end,
            )
        ).all()
    )
    new_by_date = Counter(
        _as_aware(value).astimezone(timezone).date()
        for value in risk_entries
        if value is not None
    )
    closed_by_date = Counter(
        _as_aware(record.created_at).astimezone(timezone).date()
        for record in closure_records
    )
    results = list(
        db.scalars(
            select(MatchResult)
            .options(
                selectinload(MatchResult.risk_queue_events),
                selectinload(MatchResult.handling_records),
            )
            .where(
                MatchResult.risk_entered_at.is_not(None),
                MatchResult.risk_entered_at < period_end,
            )
        ).all()
    )

    points: list[DashboardTrendPoint] = []
    cursor = start_date
    while cursor <= end_date:
        boundary = _local_day_start(cursor + timedelta(days=1), timezone)
        open_count = sum(_is_open_at(result, boundary) for result in results)
        points.append(
            DashboardTrendPoint(
                date=cursor,
                open_count=open_count,
                new_count=new_by_date[cursor],
                closed_count=closed_by_date[cursor],
            )
        )
        cursor += timedelta(days=1)
    return points


def _is_open_at(result: MatchResult, boundary: datetime) -> bool:
    entered_at = result.risk_entered_at
    if entered_at is None or _as_aware(entered_at) >= boundary:
        return False
    in_queue = False
    events = sorted(result.risk_queue_events, key=lambda item: _as_aware(item.created_at))
    if events:
        for event in events:
            if _as_aware(event.created_at) >= boundary:
                break
            in_queue = event.event_type == "entered"
    else:
        in_queue = result.status in RISK_QUEUE_STATUSES
    if not in_queue:
        return False
    handling_open = True
    records = sorted(result.handling_records, key=lambda item: _as_aware(item.created_at))
    for record in records:
        if _as_aware(record.created_at) >= boundary:
            break
        handling_open = record.to_status in OPEN_HANDLING_STATUSES
    return handling_open


def _top_risks(db: Session) -> list[DashboardTopRisk]:
    results = list(
        db.scalars(
            select(MatchResult)
            .options(
                selectinload(MatchResult.asset),
                selectinload(MatchResult.vulnerability),
            )
            .where(
                MatchResult.status.in_(RISK_QUEUE_STATUSES),
                MatchResult.handling_status.in_(OPEN_HANDLING_STATUSES),
            )
            .order_by(
                MatchResult.risk_score.desc(),
                MatchResult.risk_entered_at.asc(),
                MatchResult.updated_at.desc(),
            )
            .limit(5)
        ).all()
    )
    return [
        DashboardTopRisk(
            id=result.id,
            risk_code=result.risk_code,
            risk_priority=result.risk_priority or "none",
            risk_score=result.risk_score,
            vulnerability_id=result.vulnerability_id,
            vulnerability_canonical_id=result.vulnerability.canonical_id,
            vulnerability_title=result.vulnerability.title,
            asset_id=result.asset_id,
            asset_name=result.asset.display_name or result.asset.hostname,
            handling_status=result.handling_status,
            risk_entered_at=result.risk_entered_at,
        )
        for result in results
    ]


def _local_day_start(value: date, timezone: ZoneInfo) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone).astimezone(UTC)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
