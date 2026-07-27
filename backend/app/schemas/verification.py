from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class VerificationTaskCreateIn(BaseModel):
    match_result_id: str
    task_type: str = "package_version_check"
    parameters: dict[str, object] = Field(default_factory=dict)
    requested_by: str | None = None


class VerificationTaskRequestIn(BaseModel):
    task_type: str = "package_version_check"
    parameters: dict[str, object] = Field(default_factory=dict)
    requested_by: str | None = None


class VerificationTaskOut(BaseModel):
    id: str
    asset_id: str
    match_result_id: str
    task_type: str
    status: str
    parameters: dict[str, object] = Field(default_factory=dict)
    requested_by: str | None = None
    previous_task_id: str | None = None
    assigned_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class VerificationTaskSummaryOut(VerificationTaskOut):
    asset_hostname: str | None = None
    asset_agent_id: str | None = None
    vulnerability_id: str | None = None
    vulnerability_canonical_id: str | None = None
    vulnerability_title: str | None = None
    evidence_count: int = 0
    retry_count: int = 0


class VerificationTaskListPage(BaseModel):
    items: list[VerificationTaskSummaryOut] = Field(default_factory=list)
    offset: int = 0
    limit: int
    has_more: bool = False
    total: int = 0
    active_count: int = 0
    failed_count: int = 0
    evidence_count: int = 0


class VerificationTaskTimelineEvent(BaseModel):
    status: str
    occurred_at: datetime
    summary: str


class VerificationTaskDetailOut(VerificationTaskSummaryOut):
    evidence: list["VerificationEvidenceOut"] = Field(default_factory=list)
    timeline: list[VerificationTaskTimelineEvent] = Field(default_factory=list)


class VerificationTaskActionIn(BaseModel):
    requested_by: str | None = None


class AgentTaskOut(BaseModel):
    id: str
    task_type: str
    match_result_id: str
    parameters: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class AgentTaskPollOut(BaseModel):
    task: AgentTaskOut | None = None


class AgentTaskEvidenceIn(BaseModel):
    evidence_type: str
    summary: str
    raw_ref: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    details: dict[str, object] = Field(default_factory=dict)


class AgentTaskResultIn(BaseModel):
    status: Literal["completed", "failed", "rejected"]
    evidence: list[AgentTaskEvidenceIn] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None


class AgentTaskResultOut(BaseModel):
    status: str
    task_id: str
    evidence_count: int


class VerificationEvidenceOut(BaseModel):
    id: str
    verification_task_id: str
    evidence_type: str
    summary: str
    raw_ref: str | None = None
    confidence: float
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class VerificationEvidenceSummaryOut(VerificationEvidenceOut):
    match_result_id: str
    asset_id: str | None = None
    asset_hostname: str | None = None
    vulnerability_id: str | None = None
    vulnerability_canonical_id: str | None = None
    vulnerability_title: str | None = None


VerificationTaskDetailOut.model_rebuild()
