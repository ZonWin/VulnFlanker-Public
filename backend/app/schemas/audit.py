from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogOut(BaseModel):
    id: str
    actor_type: str
    actor_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    outcome: str
    summary: str
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class HandlingAuditRecordOut(BaseModel):
    id: str
    match_result_id: str
    risk_code: str | None = None
    vulnerability_id: str
    vulnerability_canonical_id: str
    vulnerability_title: str
    asset_id: str
    asset_hostname: str
    action: str
    from_status: str | None = None
    to_status: str
    note: str | None = None
    actor_id: str | None = None
    actor_username: str | None = None
    actor_display_name: str | None = None
    created_at: datetime
