from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.db.models import (
    Asset,
    BusinessSystem,
    MatchResult,
    Person,
    PlatformSettings,
    SystemEvent,
)
from app.schemas.email_alert import EmailActionOut
from app.services.audit import create_audit_log
from app.services.email_alerts import (
    RISK_PRIORITY_ORDER,
    create_email_delivery,
    enqueue_email_delivery,
    get_email_settings,
    normalize_recipient_email,
    priority_meets_threshold,
    render_template,
)
from app.services.match_result_handling import (
    is_closed_handling_status,
    reopen_reappeared_match_result,
)
from app.services.notifications import create_system_event
from app.services.risk_codes import RISK_CODE_STATUSES


@dataclass(frozen=True, slots=True)
class RiskStateSnapshot:
    existed: bool
    status: str
    risk_priority: str
    handling_status: str
    handling_closed_at: datetime | None


@dataclass(slots=True)
class RiskChange:
    kind: str
    result: MatchResult
    previous: RiskStateSnapshot


@dataclass(slots=True)
class RiskEvaluationOutcome:
    evaluation_event_id: str
    system_event: SystemEvent | None
    changes: list[RiskChange]
    delivery_ids: list[str]


def capture_risk_state(result: MatchResult | None) -> RiskStateSnapshot:
    if result is None:
        return RiskStateSnapshot(
            existed=False,
            status="not_evaluated",
            risk_priority="none",
            handling_status="unprocessed",
            handling_closed_at=None,
        )
    return RiskStateSnapshot(
        existed=True,
        status=result.status or "not_evaluated",
        risk_priority=result.risk_priority or "none",
        handling_status=result.handling_status or "unprocessed",
        handling_closed_at=result.handling_closed_at,
    )


def classify_risk_change(
    result: MatchResult,
    previous: RiskStateSnapshot,
) -> RiskChange | None:
    currently_risk = result.status in RISK_CODE_STATUSES
    previously_risk = previous.status in RISK_CODE_STATUSES
    if not currently_risk:
        return None
    if not previously_risk:
        kind = (
            "reappeared"
            if previous.existed and is_closed_handling_status(previous.handling_status)
            else "new"
        )
        return RiskChange(kind=kind, result=result, previous=previous)
    if RISK_PRIORITY_ORDER.get(result.risk_priority, 0) > RISK_PRIORITY_ORDER.get(
        previous.risk_priority, 0
    ):
        return RiskChange(kind="upgraded", result=result, previous=previous)
    return None


def process_risk_evaluation_changes(
    db: Session,
    *,
    changes: list[RiskChange],
    trigger_type: str,
    evaluation_event_id: str | None = None,
    occurred_at: datetime | None = None,
) -> RiskEvaluationOutcome:
    event_id = evaluation_event_id or str(uuid4())
    if not changes:
        return RiskEvaluationOutcome(event_id, None, [], [])

    for change in changes:
        if change.kind == "reappeared":
            reopen_reappeared_match_result(db, change.result)

    counts = {
        "new": sum(change.kind == "new" for change in changes),
        "upgraded": sum(change.kind == "upgraded" for change in changes),
        "reappeared": sum(change.kind == "reappeared" for change in changes),
    }
    risk_ids = [change.result.id for change in changes]
    summary = (
        f"本次{_trigger_label(trigger_type)}评估发现新增风险 {counts['new']} 项、"
        f"升级 {counts['upgraded']} 项、重新出现 {counts['reappeared']} 项。"
    )
    event = create_system_event(
        db,
        event_key=f"risk.evaluation:{event_id}",
        category="risk",
        event_type="risk_evaluation_changed",
        level="warning",
        title="风险评估发现变化",
        summary=summary,
        details={
            "evaluation_event_id": event_id,
            "trigger_type": trigger_type,
            "new_count": counts["new"],
            "upgraded_count": counts["upgraded"],
            "reappeared_count": counts["reappeared"],
            "risk_count": len(changes),
            "match_result_ids": risk_ids,
            "risks": [_risk_event_item(change) for change in changes[:100]],
        },
        target_type="risk_evaluation",
        target_id=event_id,
        target_query={"match_result_ids": risk_ids},
        occurred_at=occurred_at,
    )
    try:
        delivery_ids = _create_automatic_email_deliveries(
            db,
            event=event,
            evaluation_event_id=event_id,
            changes=changes,
        )
    except Exception as exc:
        delivery = create_email_delivery(
            db,
            trigger_type="automatic",
            recipient_email=None,
            recipient_name=None,
            source_event_id=event.id,
            dedupe_key=f"auto:{event_id}:preparation-failed",
            subject="风险邮件告警准备失败",
            text_body="",
            html_body="",
            risk_count=len(changes),
            match_result_ids=risk_ids,
            context={"threshold": None},
            skip_reason="delivery_preparation_failed",
            retry_enabled=False,
        )
        delivery.last_error = str(exc)[:2000]
        delivery_ids = [delivery.id]
    return RiskEvaluationOutcome(event_id, event, changes, delivery_ids)


def create_manual_risk_email(
    db: Session,
    match_result_id: str,
    *,
    actor_id: str,
    actor_details: dict[str, object | None] | None = None,
) -> EmailActionOut:
    result = db.scalar(
        select(MatchResult)
        .options(
            selectinload(MatchResult.asset)
            .selectinload(Asset.business_system_record)
            .selectinload(BusinessSystem.responsible_person),
            selectinload(MatchResult.vulnerability),
        )
        .where(MatchResult.id == match_result_id)
    )
    if result is None:
        raise LookupError("Match result not found.")
    settings = get_email_settings(db)
    if not settings.enabled:
        raise ValueError("Email capability is disabled.")
    if result.status not in RISK_CODE_STATUSES:
        raise ValueError("Only current risk queue items can send email alerts.")

    skip_reason = None
    if not priority_meets_threshold(result.risk_priority, settings.risk_threshold):
        skip_reason = "below_threshold"
    recipient, recipient_reason = _resolve_recipient(result)
    if skip_reason is None:
        skip_reason = recipient_reason

    subject = "风险邮件告警未发送"
    text_body = ""
    html_body = ""
    if skip_reason is None and recipient is not None:
        context = _build_template_context(db, [result], recipient.name)
        subject, text_body, html_body = _render_delivery_content(settings, context)

    delivery = create_email_delivery(
        db,
        trigger_type="manual",
        recipient_email=_person_email(recipient),
        recipient_name=recipient.name if recipient is not None else None,
        recipient_person_id=recipient.id if recipient is not None else None,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        risk_count=1,
        match_result_ids=[result.id],
        context={
            "risk_code": result.risk_code,
            "risk_priority": result.risk_priority,
            "threshold": settings.risk_threshold,
        },
        skip_reason=skip_reason,
        requested_by_user_id=actor_id,
        retry_enabled=settings.retry_enabled,
    )
    create_audit_log(
        db,
        action="email_delivery.manual_requested",
        resource_type="match_result",
        resource_id=result.id,
        actor_type="user",
        actor_id=actor_id,
        outcome="skipped" if skip_reason else "success",
        summary="Requested a manual risk email alert.",
        details={
            **(actor_details or {}),
            "delivery_id": delivery.id,
            "risk_priority": result.risk_priority,
            "threshold": settings.risk_threshold,
            "skip_reason": skip_reason,
        },
    )
    db.commit()
    if delivery.status == "queued":
        enqueue_email_delivery(delivery.id)
    return EmailActionOut(
        delivery_id=delivery.id,
        status=delivery.status,
        message=(
            "风险邮件已进入发送队列。"
            if delivery.status == "queued"
            else f"邮件未发送：{delivery.skip_reason}。"
        ),
    )


def enqueue_evaluation_deliveries(delivery_ids: list[str]) -> None:
    for delivery_id in delivery_ids:
        enqueue_email_delivery(delivery_id)


def _create_automatic_email_deliveries(
    db: Session,
    *,
    event: SystemEvent,
    evaluation_event_id: str,
    changes: list[RiskChange],
) -> list[str]:
    settings = get_email_settings(db, commit_if_created=False)
    if not settings.enabled or not settings.automatic_enabled:
        return []

    candidates = [
        change
        for change in changes
        if priority_meets_threshold(change.result.risk_priority, settings.risk_threshold)
        and (
            change.kind == "reappeared"
            or not priority_meets_threshold(
                change.previous.risk_priority, settings.risk_threshold
            )
        )
    ]
    groups: dict[str, tuple[Person, list[MatchResult]]] = {}
    delivery_ids: list[str] = []
    for change in candidates:
        result = change.result
        recipient, skip_reason = _resolve_recipient(result)
        if skip_reason is not None or recipient is None:
            delivery = create_email_delivery(
                db,
                trigger_type="automatic",
                recipient_email=_person_email(recipient),
                recipient_name=recipient.name if recipient else None,
                recipient_person_id=recipient.id if recipient else None,
                source_event_id=event.id,
                dedupe_key=f"auto:{evaluation_event_id}:risk:{result.id}",
                subject="风险邮件告警未发送",
                text_body="",
                html_body="",
                risk_count=1,
                match_result_ids=[result.id],
                context={"threshold": settings.risk_threshold},
                skip_reason=skip_reason,
                retry_enabled=settings.retry_enabled,
            )
            delivery_ids.append(delivery.id)
            continue
        group = groups.setdefault(recipient.id, (recipient, []))
        group[1].append(result)

    for person_id, (recipient, results) in groups.items():
        context = _build_template_context(db, results, recipient.name)
        subject, text_body, html_body = _render_delivery_content(settings, context)
        delivery = create_email_delivery(
            db,
            trigger_type="automatic",
            recipient_email=_person_email(recipient),
            recipient_name=recipient.name,
            recipient_person_id=recipient.id,
            source_event_id=event.id,
            dedupe_key=f"auto:{evaluation_event_id}:{person_id}",
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            risk_count=len(results),
            match_result_ids=[result.id for result in results],
            context={
                "threshold": settings.risk_threshold,
                "business_system_ids": sorted(
                    {
                        result.asset.business_system_id
                        for result in results
                        if result.asset.business_system_id
                    }
                ),
            },
            retry_enabled=settings.retry_enabled,
        )
        delivery_ids.append(delivery.id)
    return delivery_ids


def _resolve_recipient(result: MatchResult) -> tuple[Person | None, str | None]:
    system = result.asset.business_system_record
    if system is None:
        return None, "missing_business_system"
    if system.status != "active":
        return None, "inactive_business_system"
    person = system.responsible_person
    if person is None:
        return None, "missing_responsible_person"
    if person.status != "active":
        return person, "inactive_responsible_person"
    if not person.email:
        return person, "missing_recipient_email"
    try:
        normalize_recipient_email(person.email)
    except ValueError:
        return person, "invalid_recipient_email"
    return person, None


def _render_delivery_content(settings, context: dict[str, str]) -> tuple[str, str, str]:
    return (
        render_template(settings.subject_template, context, html_mode=False)[:500],
        render_template(settings.text_body_template, context, html_mode=False),
        render_template(settings.html_body_template, context, html_mode=True),
    )


def _build_template_context(
    db: Session,
    results: list[MatchResult],
    recipient_name: str,
) -> dict[str, str]:
    platform = db.get(PlatformSettings, "default")
    platform_name = platform.platform_name if platform is not None else "VulnFlanker"
    sorted_results = sorted(
        results,
        key=lambda item: RISK_PRIORITY_ORDER.get(item.risk_priority, 0),
        reverse=True,
    )
    highest = sorted_results[0].risk_priority if sorted_results else "none"
    systems = sorted(
        {
            result.asset.business_system_record.name
            for result in results
            if result.asset.business_system_record is not None
        }
    )
    risk_codes = [result.risk_code or result.id for result in sorted_results]
    text_lines = []
    html_rows = []
    for index, result in enumerate(sorted_results, start=1):
        vulnerability = result.vulnerability
        asset = result.asset
        code = result.risk_code or result.id
        text_lines.append(
            f"{index}. {code} / {result.risk_priority} / "
            f"{vulnerability.canonical_id} / {asset.hostname}"
        )
        html_rows.append(
            "<tr>"
            f"<td>{html.escape(code)}</td>"
            f"<td>{html.escape(result.risk_priority)}</td>"
            f"<td>{html.escape(vulnerability.canonical_id)}</td>"
            f"<td>{html.escape(asset.hostname)}</td>"
            "</tr>"
        )
    risk_list_html = (
        "<table><thead><tr><th>风险</th><th>等级</th><th>漏洞</th><th>资产</th>"
        "</tr></thead><tbody>"
        + "".join(html_rows)
        + "</tbody></table>"
    )
    return {
        "platform_name": platform_name,
        "recipient_name": recipient_name,
        "risk_count": str(len(results)),
        "highest_priority": highest,
        "risk_codes": ", ".join(risk_codes),
        "business_systems": ", ".join(systems),
        "risk_list_text": "\n".join(text_lines),
        "risk_list_html": risk_list_html,
        "generated_at": utcnow().isoformat(),
    }


def _risk_event_item(change: RiskChange) -> dict[str, str | None]:
    result = change.result
    return {
        "match_result_id": result.id,
        "risk_code": result.risk_code,
        "change_kind": change.kind,
        "previous_priority": change.previous.risk_priority,
        "current_priority": result.risk_priority,
        "asset_id": result.asset_id,
        "asset_hostname": result.asset.hostname,
        "vulnerability_id": result.vulnerability_id,
        "vulnerability_canonical_id": result.vulnerability.canonical_id,
    }


def _trigger_label(trigger_type: str) -> str:
    return "自动" if trigger_type == "automatic" else "手动"


def _person_email(person: Person | None) -> str | None:
    if person is None or not person.email:
        return None
    return person.email.strip()
