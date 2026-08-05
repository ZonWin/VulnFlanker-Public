from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SmtpSecurity = Literal["starttls", "ssl_tls", "none"]
RiskThreshold = Literal["low", "medium", "high", "critical"]
EmailDeliveryStatus = Literal[
    "queued", "sending", "retry_scheduled", "sent", "failed", "skipped"
]
EmailTriggerType = Literal["automatic", "manual", "test", "manual_retry"]


class EmailSettingsOut(BaseModel):
    id: str = "default"
    enabled: bool
    automatic_enabled: bool
    risk_threshold: RiskThreshold
    retry_enabled: bool
    retry_delays_seconds: list[int]
    smtp_host: str | None = None
    smtp_port: int
    smtp_security: SmtpSecurity
    smtp_username: str | None = None
    has_password: bool
    sender_name: str | None = None
    sender_email: str | None = None
    reply_to: str | None = None
    timeout_seconds: int
    subject_template: str
    text_body_template: str
    html_body_template: str
    supported_template_variables: list[str]
    version: int
    updated_at: datetime


class EmailSettingsUpdate(BaseModel):
    enabled: bool | None = None
    automatic_enabled: bool | None = None
    risk_threshold: RiskThreshold | None = None
    retry_enabled: bool | None = None
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_security: SmtpSecurity | None = None
    smtp_username: str | None = Field(default=None, max_length=320)
    smtp_password: str | None = Field(default=None, max_length=2048)
    clear_password: bool = False
    sender_name: str | None = Field(default=None, max_length=255)
    sender_email: str | None = Field(default=None, max_length=320)
    reply_to: str | None = Field(default=None, max_length=320)
    timeout_seconds: int | None = Field(default=None, ge=5, le=60)
    subject_template: str | None = Field(default=None, max_length=500)
    text_body_template: str | None = Field(default=None, max_length=50_000)
    html_body_template: str | None = Field(default=None, max_length=100_000)
    expected_version: int | None = Field(default=None, ge=1)


class EmailTemplatePreviewIn(BaseModel):
    subject_template: str = Field(max_length=500)
    text_body_template: str = Field(max_length=50_000)
    html_body_template: str = Field(max_length=100_000)


class EmailTemplatePreviewOut(BaseModel):
    subject: str
    text_body: str
    html_body: str


class TestEmailIn(BaseModel):
    recipient_email: str = Field(min_length=3, max_length=320)


class EmailDeliveryAttemptOut(BaseModel):
    id: str
    attempt_number: int
    status: Literal["sent", "failed"]
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime


class EmailDeliveryOut(BaseModel):
    id: str
    trigger_type: EmailTriggerType
    status: EmailDeliveryStatus
    source_event_id: str | None = None
    retry_of_id: str | None = None
    recipient_person_id: str | None = None
    recipient_name: str | None = None
    recipient_email: str | None = None
    subject: str
    risk_count: int
    match_result_ids: list[str] = Field(default_factory=list)
    context: dict[str, object] = Field(default_factory=dict)
    skip_reason: str | None = None
    last_error: str | None = None
    attempt_count: int
    max_retries: int
    next_attempt_at: datetime | None = None
    last_attempt_at: datetime | None = None
    sent_at: datetime | None = None
    requested_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class EmailDeliveryDetailOut(EmailDeliveryOut):
    text_body: str
    html_body: str
    attempts: list[EmailDeliveryAttemptOut] = Field(default_factory=list)


class EmailDeliveryListPage(BaseModel):
    items: list[EmailDeliveryOut]
    total: int
    offset: int
    limit: int


class EmailActionOut(BaseModel):
    delivery_id: str
    status: EmailDeliveryStatus
    message: str
