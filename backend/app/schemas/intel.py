from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntelCollectRequest(BaseModel):
    limit: int | None = Field(default=None, ge=0, le=5000)
    min_score: float | None = Field(default=None, ge=0, le=10)
    async_mode: bool = False
    latest_only: bool = True


class WatchVulnMonitorConfigUpdate(BaseModel):
    enabled: bool | None = None
    interval_seconds: int | None = Field(default=None, ge=60, le=86_400)
    limit: int | None = Field(default=None, ge=1, le=5000)


class CisaKevMonitorConfigUpdate(BaseModel):
    enabled: bool | None = None
    interval_seconds: int | None = Field(default=None, ge=300, le=604_800)
    limit: int | None = Field(default=None, ge=1, le=5000)
    latest_only: bool | None = None


class WatchVulnMonitorConfigOut(BaseModel):
    enabled: bool
    interval_seconds: int
    limit: int | None
    last_run_id: str | None = None
    last_status: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_error: str | None = None
    next_run_at: datetime | None = None
    updated_at: datetime


class CisaKevMonitorConfigOut(BaseModel):
    enabled: bool
    interval_seconds: int
    limit: int | None
    latest_only: bool
    last_run_id: str | None = None
    last_status: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_error: str | None = None
    next_run_at: datetime | None = None
    updated_at: datetime


class IntelCollectionResult(BaseModel):
    status: str
    source_name: str
    run_id: str | None = None
    fetched_count: int = 0
    stored_count: int = 0
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    task_id: str | None = None
    error_message: str | None = None
    message: str | None = None


class IntelSourceVulnerabilityCleanupRequest(BaseModel):
    confirmed: bool = False


class IntelSourceVulnerabilityCleanupResult(BaseModel):
    source_name: str
    source_label: str | None = None
    source_links_deleted: int = 0
    vulnerabilities_deleted: int = 0
    shared_vulnerabilities_retained: int = 0
    raw_events_deleted: int = 0
    collection_runs_deleted: int = 0
    match_results_deleted: int = 0
    verification_tasks_deleted: int = 0
    ai_enrichments_deleted: int = 0
    affected_scopes_deleted: int = 0
    review_resolutions_deleted: int = 0


class WatchVulnVulnInfo(BaseModel):
    unique_key: str | None = None
    title: str
    description: str | None = None
    severity: str | None = None
    cve: str | None = None
    disclosure: str | None = None
    solutions: str | None = None
    github_search: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    from_: str | None = Field(default=None, alias="from")
    reason: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class WatchVulnWebhookEnvelope(BaseModel):
    type: str
    content: dict[str, Any]


class IntelWebhookAccepted(BaseModel):
    raw_event_id: str
    provider: str
    event_type: str
    processing_status: str
    run_id: str | None = None
    deduplicated: bool = False
    queued: bool = False


class IntelCollectionRunOut(BaseModel):
    id: str
    source_name: str
    trigger_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    fetched_count: int
    stored_count: int
    processed_count: int
    skipped_count: int
    failed_count: int
    error_message: str | None
    task_id: str | None
    parameters: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class IntelSourceStatusOut(BaseModel):
    source_name: str
    source_label: str | None = None
    parent_source_name: str | None = None
    enabled: bool
    last_run_id: str | None = None
    last_status: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_error: str | None = None
    raw_event_count: int = 0
    processed_event_count: int = 0
    failed_event_count: int = 0
    vulnerability_count: int = 0


class IntelNormalizationQualityOut(BaseModel):
    has_canonical_id: bool
    has_product: bool
    has_affected_version: bool
    has_fixed_version: bool
    has_severity: bool
    has_exploitation_signal: bool
    source_url_count: int = 0
    reference_count: int = 0
    missing_fields: list[str] = Field(default_factory=list)
    issue_codes: list[str] = Field(default_factory=list)
    conflict_fields: list[str] = Field(default_factory=list)
    source_conflict_count: int = 0
    needs_ai_enrichment: bool = False
    needs_human_review: bool = False


class IntelRawEventOut(BaseModel):
    id: str
    provider: str
    event_type: str
    external_key: str
    source_url: str | None
    processing_status: str
    received_at: datetime
    processed_at: datetime | None
    last_error: str | None
    vulnerability_id: str | None
    vulnerability_canonical_id: str | None
    quality: IntelNormalizationQualityOut | None
    created_at: datetime
    updated_at: datetime


class IntelRawEventNormalizeResult(BaseModel):
    raw_event_id: str
    status: str
    vulnerability_id: str | None = None
    canonical_id: str | None = None
