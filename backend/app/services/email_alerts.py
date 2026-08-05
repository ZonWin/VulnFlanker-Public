from __future__ import annotations

import html
import re
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.db.models import (
    EmailDelivery,
    EmailDeliveryAttempt,
    EmailSettings,
)
from app.schemas.email_alert import (
    EmailActionOut,
    EmailDeliveryAttemptOut,
    EmailDeliveryDetailOut,
    EmailDeliveryListPage,
    EmailDeliveryOut,
    EmailSettingsOut,
    EmailSettingsUpdate,
    EmailTemplatePreviewOut,
)
from app.services.audit import create_audit_log
from app.services.secret_crypto import decrypt_secret, encrypt_secret


EMAIL_SETTINGS_ID = "default"
RETRY_DELAYS_SECONDS = (60, 300, 1800)
RISK_PRIORITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
SUPPORTED_TEMPLATE_VARIABLES = (
    "platform_name",
    "recipient_name",
    "risk_count",
    "highest_priority",
    "risk_codes",
    "business_systems",
    "risk_list_text",
    "risk_list_html",
    "generated_at",
)
DEFAULT_SUBJECT_TEMPLATE = "[{{platform_name}}] {{risk_count}} 项风险告警（最高 {{highest_priority}}）"
DEFAULT_TEXT_BODY_TEMPLATE = """{{recipient_name}}，您好：

{{platform_name}} 检测到 {{risk_count}} 项需要关注的风险，最高等级为 {{highest_priority}}。

{{risk_list_text}}

涉及业务系统：{{business_systems}}
生成时间：{{generated_at}}
"""
DEFAULT_HTML_BODY_TEMPLATE = """<p>{{recipient_name}}，您好：</p>
<p><strong>{{platform_name}}</strong> 检测到 {{risk_count}} 项需要关注的风险，最高等级为 <strong>{{highest_priority}}</strong>。</p>
{{risk_list_html}}
<p>涉及业务系统：{{business_systems}}</p>
<p>生成时间：{{generated_at}}</p>
"""

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_TEMPLATE_VARIABLE_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
_ANY_TEMPLATE_TOKEN_PATTERN = re.compile(r"{{|}}")
_DANGEROUS_HTML_PATTERN = re.compile(
    r"<(?:script|iframe|object|embed)\b|\son[a-z]+\s*=|javascript\s*:",
    re.IGNORECASE,
)


def get_email_settings(
    db: Session,
    *,
    commit_if_created: bool = True,
) -> EmailSettings:
    settings = db.get(EmailSettings, EMAIL_SETTINGS_ID)
    if settings is not None:
        return settings
    settings = EmailSettings(
        id=EMAIL_SETTINGS_ID,
        enabled=False,
        automatic_enabled=False,
        risk_threshold="high",
        retry_enabled=True,
        smtp_host=None,
        smtp_port=587,
        smtp_security="starttls",
        smtp_username=None,
        smtp_password_ciphertext=None,
        sender_name="VulnFlanker",
        sender_email=None,
        reply_to=None,
        timeout_seconds=15,
        subject_template=DEFAULT_SUBJECT_TEMPLATE,
        text_body_template=DEFAULT_TEXT_BODY_TEMPLATE,
        html_body_template=DEFAULT_HTML_BODY_TEMPLATE,
    )
    db.add(settings)
    if commit_if_created:
        db.commit()
        db.refresh(settings)
    else:
        db.flush()
    return settings


def get_email_settings_out(db: Session) -> EmailSettingsOut:
    return _settings_out(get_email_settings(db))


def update_email_settings(
    db: Session,
    payload: EmailSettingsUpdate,
    *,
    actor_id: str,
    actor_details: dict[str, object | None] | None = None,
) -> EmailSettingsOut:
    settings = get_email_settings(db)
    if payload.expected_version is not None and payload.expected_version != settings.version:
        raise ValueError("Email settings were updated by another request. Refresh and retry.")
    fields = payload.model_fields_set

    for field in ("enabled", "automatic_enabled", "retry_enabled"):
        if field in fields and getattr(payload, field) is not None:
            setattr(settings, field, getattr(payload, field))
    if "risk_threshold" in fields and payload.risk_threshold is not None:
        settings.risk_threshold = payload.risk_threshold
    if "smtp_host" in fields:
        settings.smtp_host = _optional_text(payload.smtp_host)
    if "smtp_port" in fields and payload.smtp_port is not None:
        settings.smtp_port = payload.smtp_port
    if "smtp_security" in fields and payload.smtp_security is not None:
        settings.smtp_security = payload.smtp_security
    if "smtp_username" in fields:
        settings.smtp_username = _optional_text(payload.smtp_username)
    if payload.clear_password:
        settings.smtp_password_ciphertext = None
    elif "smtp_password" in fields and payload.smtp_password:
        settings.smtp_password_ciphertext = encrypt_secret(payload.smtp_password)
    if "sender_name" in fields:
        settings.sender_name = _optional_header_text(payload.sender_name, "sender_name")
    if "sender_email" in fields:
        settings.sender_email = _optional_email(payload.sender_email, "sender_email")
    if "reply_to" in fields:
        settings.reply_to = _optional_email(payload.reply_to, "reply_to")
    if "timeout_seconds" in fields and payload.timeout_seconds is not None:
        settings.timeout_seconds = payload.timeout_seconds
    if "subject_template" in fields and payload.subject_template is not None:
        settings.subject_template = _validate_template(
            payload.subject_template, field="subject_template", subject=True
        )
    if "text_body_template" in fields and payload.text_body_template is not None:
        settings.text_body_template = _validate_template(
            payload.text_body_template, field="text_body_template"
        )
    if "html_body_template" in fields and payload.html_body_template is not None:
        settings.html_body_template = _validate_template(
            payload.html_body_template, field="html_body_template", html_body=True
        )

    _validate_settings_ready(settings)
    db.add(settings)
    create_audit_log(
        db,
        action="email_settings.updated",
        resource_type="email_settings",
        resource_id=settings.id,
        actor_type="user",
        actor_id=actor_id,
        summary="Updated email alert settings.",
        details={
            **(actor_details or {}),
            "updated_fields": sorted(field for field in fields if field != "smtp_password"),
            "smtp_password_updated": "smtp_password" in fields,
            "smtp_password_cleared": payload.clear_password,
            "enabled": settings.enabled,
            "automatic_enabled": settings.automatic_enabled,
            "risk_threshold": settings.risk_threshold,
            "retry_enabled": settings.retry_enabled,
        },
    )
    db.commit()
    db.refresh(settings)
    return _settings_out(settings)


def preview_email_templates(
    *, subject_template: str, text_body_template: str, html_body_template: str
) -> EmailTemplatePreviewOut:
    subject = _validate_template(subject_template, field="subject_template", subject=True)
    text_body = _validate_template(text_body_template, field="text_body_template")
    html_body = _validate_template(
        html_body_template, field="html_body_template", html_body=True
    )
    context = sample_template_context()
    return EmailTemplatePreviewOut(
        subject=render_template(subject, context, html_mode=False),
        text_body=render_template(text_body, context, html_mode=False),
        html_body=render_template(html_body, context, html_mode=True),
    )


def sample_template_context() -> dict[str, str]:
    return {
        "platform_name": "VulnFlanker",
        "recipient_name": "示例责任人",
        "risk_count": "2",
        "highest_priority": "critical",
        "risk_codes": "RISK-20260805-0001, RISK-20260805-0002",
        "business_systems": "核心交易系统, 统一认证系统",
        "risk_list_text": (
            "1. RISK-20260805-0001 / critical / CVE-2026-0001 / core-app-01\n"
            "2. RISK-20260805-0002 / high / CVE-2026-0002 / auth-app-01"
        ),
        "risk_list_html": (
            "<table><thead><tr><th>风险</th><th>等级</th><th>漏洞</th><th>资产</th></tr></thead>"
            "<tbody><tr><td>RISK-20260805-0001</td><td>critical</td>"
            "<td>CVE-2026-0001</td><td>core-app-01</td></tr>"
            "<tr><td>RISK-20260805-0002</td><td>high</td>"
            "<td>CVE-2026-0002</td><td>auth-app-01</td></tr></tbody></table>"
        ),
        "generated_at": "2026-08-05 18:00:00 +08:00",
    }


def render_template(template: str, context: dict[str, Any], *, html_mode: bool) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in SUPPORTED_TEMPLATE_VARIABLES:
            raise ValueError(f"Unsupported template variable: {name}")
        value = str(context.get(name, ""))
        if html_mode and name != "risk_list_html":
            return html.escape(value)
        return value

    return _TEMPLATE_VARIABLE_PATTERN.sub(replace, template)


def create_email_delivery(
    db: Session,
    *,
    trigger_type: str,
    recipient_email: str | None,
    recipient_name: str | None,
    subject: str,
    text_body: str,
    html_body: str,
    recipient_person_id: str | None = None,
    source_event_id: str | None = None,
    retry_of_id: str | None = None,
    dedupe_key: str | None = None,
    risk_count: int = 0,
    match_result_ids: list[str] | None = None,
    context: dict[str, Any] | None = None,
    skip_reason: str | None = None,
    requested_by_user_id: str | None = None,
    retry_enabled: bool = True,
) -> EmailDelivery:
    if dedupe_key:
        existing = db.scalar(
            select(EmailDelivery).where(EmailDelivery.dedupe_key == dedupe_key)
        )
        if existing is not None:
            return existing
    delivery = EmailDelivery(
        trigger_type=trigger_type,
        status="skipped" if skip_reason else "queued",
        dedupe_key=dedupe_key,
        source_event_id=source_event_id,
        retry_of_id=retry_of_id,
        recipient_person_id=recipient_person_id,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        risk_count=risk_count,
        match_result_ids_json=match_result_ids or [],
        context_json=context or {},
        skip_reason=skip_reason,
        max_retries=len(RETRY_DELAYS_SECONDS) if retry_enabled else 0,
        requested_by_user_id=requested_by_user_id,
    )
    db.add(delivery)
    db.flush()
    return delivery


def create_test_email_delivery(
    db: Session,
    *,
    recipient_email: str,
    actor_id: str,
    actor_details: dict[str, object | None] | None = None,
) -> EmailActionOut:
    settings = get_email_settings(db)
    _require_email_enabled(settings)
    _validate_settings_ready(settings)
    recipient = _required_email(recipient_email, "recipient_email")
    context = sample_template_context()
    delivery = create_email_delivery(
        db,
        trigger_type="test",
        recipient_email=recipient,
        recipient_name="测试收件人",
        subject=f"[{context['platform_name']}] 邮件服务器测试",
        text_body="VulnFlanker 邮件服务器配置测试成功。",
        html_body="<p><strong>VulnFlanker</strong> 邮件服务器配置测试成功。</p>",
        context={"test": True},
        requested_by_user_id=actor_id,
        retry_enabled=settings.retry_enabled,
    )
    create_audit_log(
        db,
        action="email_delivery.test_requested",
        resource_type="email_delivery",
        resource_id=delivery.id,
        actor_type="user",
        actor_id=actor_id,
        summary="Requested a test email delivery.",
        details={**(actor_details or {}), "recipient_email": recipient},
    )
    db.commit()
    enqueue_email_delivery(delivery.id)
    return EmailActionOut(
        delivery_id=delivery.id,
        status=delivery.status,
        message="测试邮件已进入发送队列。",
    )


def list_email_deliveries(
    db: Session,
    *,
    status: str | None = None,
    trigger_type: str | None = None,
    recipient_email: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> EmailDeliveryListPage:
    conditions = []
    if status:
        conditions.append(EmailDelivery.status == status)
    if trigger_type:
        conditions.append(EmailDelivery.trigger_type == trigger_type)
    if recipient_email:
        conditions.append(EmailDelivery.recipient_email.ilike(f"%{recipient_email.strip()}%"))
    total = int(db.scalar(select(func.count(EmailDelivery.id)).where(*conditions)) or 0)
    statement = (
        select(EmailDelivery)
        .where(*conditions)
        .order_by(desc(EmailDelivery.created_at))
        .offset(offset)
        .limit(limit)
    )
    return EmailDeliveryListPage(
        items=[_delivery_out(item) for item in db.scalars(statement).all()],
        total=total,
        offset=offset,
        limit=limit,
    )


def get_email_delivery_detail(
    db: Session, delivery_id: str
) -> EmailDeliveryDetailOut | None:
    delivery = db.scalar(
        select(EmailDelivery)
        .options(selectinload(EmailDelivery.attempts))
        .where(EmailDelivery.id == delivery_id)
    )
    return _delivery_detail_out(delivery) if delivery is not None else None


def resend_failed_email_delivery(
    db: Session,
    delivery_id: str,
    *,
    actor_id: str,
    actor_details: dict[str, object | None] | None = None,
) -> EmailActionOut:
    original = db.get(EmailDelivery, delivery_id)
    if original is None:
        raise LookupError("Email delivery not found.")
    if original.status != "failed":
        raise ValueError("Only failed email deliveries can be resent.")
    settings = get_email_settings(db)
    _require_email_enabled(settings)
    delivery = create_email_delivery(
        db,
        trigger_type="manual_retry",
        recipient_email=original.recipient_email,
        recipient_name=original.recipient_name,
        recipient_person_id=original.recipient_person_id,
        retry_of_id=original.id,
        source_event_id=original.source_event_id,
        subject=original.subject,
        text_body=original.text_body,
        html_body=original.html_body,
        risk_count=original.risk_count,
        match_result_ids=list(original.match_result_ids_json or []),
        context=dict(original.context_json or {}),
        requested_by_user_id=actor_id,
        retry_enabled=settings.retry_enabled,
    )
    create_audit_log(
        db,
        action="email_delivery.resent",
        resource_type="email_delivery",
        resource_id=delivery.id,
        actor_type="user",
        actor_id=actor_id,
        summary="Resent a failed email delivery.",
        details={**(actor_details or {}), "retry_of_id": original.id},
    )
    db.commit()
    enqueue_email_delivery(delivery.id)
    return EmailActionOut(
        delivery_id=delivery.id,
        status=delivery.status,
        message="失败邮件已重新进入发送队列。",
    )


def enqueue_email_delivery(delivery_id: str) -> bool:
    try:
        from app.workers.tasks import send_email_delivery_task

        send_email_delivery_task.delay(delivery_id)
        return True
    except Exception:
        return False


def due_email_delivery_ids(db: Session, *, limit: int = 100) -> list[str]:
    now = utcnow()
    rows = db.scalars(
        select(EmailDelivery.id)
        .where(
            or_(
                EmailDelivery.status == "queued",
                and_(
                    EmailDelivery.status == "retry_scheduled",
                    EmailDelivery.next_attempt_at <= now,
                ),
            )
        )
        .order_by(EmailDelivery.created_at)
        .limit(limit)
    ).all()
    return list(rows)


def recover_stale_email_deliveries(db: Session, *, stale_minutes: int = 10) -> int:
    cutoff = utcnow() - timedelta(minutes=stale_minutes)
    deliveries = db.scalars(
        select(EmailDelivery).where(
            EmailDelivery.status == "sending",
            EmailDelivery.updated_at < cutoff,
        )
    ).all()
    for delivery in deliveries:
        delivery.status = "queued"
        delivery.last_error = "Recovered a stale in-progress delivery."
        db.add(delivery)
    if deliveries:
        db.commit()
    return len(deliveries)


def send_email_delivery(db: Session, delivery_id: str) -> EmailDelivery | None:
    delivery = db.scalar(
        select(EmailDelivery)
        .options(selectinload(EmailDelivery.attempts))
        .where(EmailDelivery.id == delivery_id)
        .with_for_update()
    )
    if delivery is None:
        return None
    if delivery.status not in {"queued", "retry_scheduled"}:
        return delivery
    if delivery.status == "retry_scheduled" and (
        delivery.next_attempt_at is None or delivery.next_attempt_at > utcnow()
    ):
        return delivery
    settings = get_email_settings(db)
    if not settings.enabled:
        delivery.status = "failed"
        delivery.last_error = "Email capability is disabled."
        delivery.next_attempt_at = None
        db.add(delivery)
        db.commit()
        return delivery

    delivery.status = "sending"
    delivery.next_attempt_at = None
    db.add(delivery)
    db.commit()

    started_at = utcnow()
    attempt_number = delivery.attempt_count + 1
    try:
        _smtp_send(settings, delivery)
    except Exception as exc:
        finished_at = utcnow()
        error_message = _safe_error(exc)
        delivery.attempt_count = attempt_number
        delivery.last_attempt_at = finished_at
        delivery.last_error = error_message
        delivery.attempts.append(
            EmailDeliveryAttempt(
                attempt_number=attempt_number,
                status="failed",
                error_message=error_message,
                started_at=started_at,
                finished_at=finished_at,
            )
        )
        if attempt_number <= delivery.max_retries:
            delay = RETRY_DELAYS_SECONDS[attempt_number - 1]
            delivery.status = "retry_scheduled"
            delivery.next_attempt_at = finished_at + timedelta(seconds=delay)
        else:
            delivery.status = "failed"
            delivery.next_attempt_at = None
        db.add(delivery)
        db.commit()
        return delivery

    finished_at = utcnow()
    delivery.attempt_count = attempt_number
    delivery.last_attempt_at = finished_at
    delivery.sent_at = finished_at
    delivery.status = "sent"
    delivery.last_error = None
    delivery.next_attempt_at = None
    delivery.attempts.append(
        EmailDeliveryAttempt(
            attempt_number=attempt_number,
            status="sent",
            error_message=None,
            started_at=started_at,
            finished_at=finished_at,
        )
    )
    db.add(delivery)
    db.commit()
    return delivery


def priority_meets_threshold(priority: str, threshold: str) -> bool:
    return RISK_PRIORITY_ORDER.get(priority, 0) >= RISK_PRIORITY_ORDER.get(threshold, 0)


def normalize_recipient_email(value: str) -> str:
    return _required_email(value, "recipient_email")


def _smtp_send(settings: EmailSettings, delivery: EmailDelivery) -> None:
    _validate_settings_ready(settings)
    if not delivery.recipient_email:
        raise ValueError("Recipient email is missing.")
    password = decrypt_secret(settings.smtp_password_ciphertext)
    message = EmailMessage()
    message["Subject"] = delivery.subject
    message["From"] = formataddr((settings.sender_name or "", settings.sender_email or ""))
    message["To"] = delivery.recipient_email
    if settings.reply_to:
        message["Reply-To"] = settings.reply_to
    message.set_content(delivery.text_body or " ")
    if delivery.html_body:
        message.add_alternative(delivery.html_body, subtype="html")

    context = ssl.create_default_context()
    smtp: smtplib.SMTP
    if settings.smtp_security == "ssl_tls":
        smtp = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.timeout_seconds,
            context=context,
        )
    else:
        smtp = smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.timeout_seconds,
        )
    try:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=context)
        if settings.smtp_username:
            smtp.login(settings.smtp_username, password or "")
        smtp.send_message(message)
    finally:
        try:
            smtp.quit()
        except Exception:
            smtp.close()


def _validate_settings_ready(settings: EmailSettings) -> None:
    _validate_template(settings.subject_template, field="subject_template", subject=True)
    _validate_template(settings.text_body_template, field="text_body_template")
    _validate_template(
        settings.html_body_template, field="html_body_template", html_body=True
    )
    if not settings.enabled:
        return
    if not _optional_text(settings.smtp_host):
        raise ValueError("SMTP host is required when email is enabled.")
    _required_email(settings.sender_email or "", "sender_email")
    if settings.smtp_username and not settings.smtp_password_ciphertext:
        raise ValueError("SMTP password is required when a username is configured.")


def _require_email_enabled(settings: EmailSettings) -> None:
    if not settings.enabled:
        raise ValueError("Email capability is disabled.")


def _validate_template(
    value: str,
    *,
    field: str,
    subject: bool = False,
    html_body: bool = False,
) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} cannot be empty.")
    if subject and ("\r" in normalized or "\n" in normalized):
        raise ValueError("subject_template cannot contain line breaks.")
    if html_body and _DANGEROUS_HTML_PATTERN.search(normalized):
        raise ValueError("html_body_template contains unsafe HTML.")
    variables = _TEMPLATE_VARIABLE_PATTERN.findall(normalized)
    unsupported = sorted(set(variables) - set(SUPPORTED_TEMPLATE_VARIABLES))
    if unsupported:
        raise ValueError(f"Unsupported template variables: {', '.join(unsupported)}")
    without_valid_tokens = _TEMPLATE_VARIABLE_PATTERN.sub("", normalized)
    if _ANY_TEMPLATE_TOKEN_PATTERN.search(without_valid_tokens):
        raise ValueError(f"{field} contains an incomplete template token.")
    if field != "html_body_template" and "risk_list_html" in variables:
        raise ValueError("risk_list_html is only allowed in html_body_template.")
    if field == "html_body_template" and "risk_list_text" in variables:
        raise ValueError("risk_list_text is only allowed in text_body_template.")
    return normalized


def _optional_text(value: str | None) -> str | None:
    normalized = value.strip() if value is not None else ""
    return normalized or None


def _optional_header_text(value: str | None, field: str) -> str | None:
    normalized = _optional_text(value)
    if normalized and ("\r" in normalized or "\n" in normalized):
        raise ValueError(f"{field} cannot contain line breaks.")
    return normalized


def _required_email(value: str, field: str) -> str:
    normalized = value.strip()
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field} must be a valid email address.")
    if "\r" in normalized or "\n" in normalized:
        raise ValueError(f"{field} cannot contain line breaks.")
    return normalized


def _optional_email(value: str | None, field: str) -> str | None:
    normalized = _optional_text(value)
    return _required_email(normalized, field) if normalized else None


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    message = re.sub(r"(?i)(password|authorization|token|secret)\s*[:=]\s*\S+", r"\1=[redacted]", message)
    return message[:2000]


def _settings_out(settings: EmailSettings) -> EmailSettingsOut:
    return EmailSettingsOut(
        id=settings.id,
        enabled=settings.enabled,
        automatic_enabled=settings.automatic_enabled,
        risk_threshold=settings.risk_threshold,
        retry_enabled=settings.retry_enabled,
        retry_delays_seconds=list(RETRY_DELAYS_SECONDS),
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_security=settings.smtp_security,
        smtp_username=settings.smtp_username,
        has_password=bool(settings.smtp_password_ciphertext),
        sender_name=settings.sender_name,
        sender_email=settings.sender_email,
        reply_to=settings.reply_to,
        timeout_seconds=settings.timeout_seconds,
        subject_template=settings.subject_template,
        text_body_template=settings.text_body_template,
        html_body_template=settings.html_body_template,
        supported_template_variables=list(SUPPORTED_TEMPLATE_VARIABLES),
        version=settings.version,
        updated_at=settings.updated_at,
    )


def _delivery_out(delivery: EmailDelivery) -> EmailDeliveryOut:
    return EmailDeliveryOut(
        id=delivery.id,
        trigger_type=delivery.trigger_type,
        status=delivery.status,
        source_event_id=delivery.source_event_id,
        retry_of_id=delivery.retry_of_id,
        recipient_person_id=delivery.recipient_person_id,
        recipient_name=delivery.recipient_name,
        recipient_email=delivery.recipient_email,
        subject=delivery.subject,
        risk_count=delivery.risk_count,
        match_result_ids=list(delivery.match_result_ids_json or []),
        context=delivery.context_json or {},
        skip_reason=delivery.skip_reason,
        last_error=delivery.last_error,
        attempt_count=delivery.attempt_count,
        max_retries=delivery.max_retries,
        next_attempt_at=delivery.next_attempt_at,
        last_attempt_at=delivery.last_attempt_at,
        sent_at=delivery.sent_at,
        requested_by_user_id=delivery.requested_by_user_id,
        created_at=delivery.created_at,
        updated_at=delivery.updated_at,
    )


def _delivery_detail_out(delivery: EmailDelivery) -> EmailDeliveryDetailOut:
    base = _delivery_out(delivery).model_dump()
    return EmailDeliveryDetailOut(
        **base,
        text_body=delivery.text_body,
        html_body=delivery.html_body,
        attempts=[
            EmailDeliveryAttemptOut(
                id=item.id,
                attempt_number=item.attempt_number,
                status=item.status,
                error_message=item.error_message,
                started_at=item.started_at,
                finished_at=item.finished_at,
            )
            for item in delivery.attempts
        ],
    )
