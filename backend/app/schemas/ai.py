from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.vulnerability import VulnerabilityDetail, VulnerabilityReadinessOut


class AIPromptTemplateUpdate(BaseModel):
    system_prompt: str = Field(min_length=1, max_length=50_000)
    user_prompt_template: str = Field(min_length=1, max_length=50_000)
    output_contract: str = Field(min_length=1, max_length=50_000)


class AIProfileCreate(BaseModel):
    profile_key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=64)
    model_vendor: str = Field(default="openai", min_length=1, max_length=64)
    base_url: str | None = None
    api_key: str | None = Field(default=None, max_length=4096)
    model: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    supports_web_search: bool = False
    allow_external_network: bool = False
    json_mode: bool = True
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_tokens: int | None = Field(default=None, ge=1, le=100_000)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    daily_call_limit: int | None = Field(default=None, ge=1)
    daily_token_limit: int | None = Field(default=None, ge=1)
    prompt_template: AIPromptTemplateUpdate | None = None


class AIProfileUpdate(BaseModel):
    profile_key: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    model_vendor: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = None
    api_key: str | None = Field(default=None, max_length=4096)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    supports_web_search: bool | None = None
    allow_external_network: bool | None = None
    json_mode: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    max_tokens: int | None = Field(default=None, ge=1, le=100_000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    daily_call_limit: int | None = Field(default=None, ge=1)
    daily_token_limit: int | None = Field(default=None, ge=1)
    prompt_template: AIPromptTemplateUpdate | None = None


class AIPromptTemplateOut(BaseModel):
    template_key: str
    system_prompt: str
    user_prompt_template: str
    output_contract: str
    customized: bool = False


class AIProfileOut(BaseModel):
    id: str
    profile_key: str
    display_name: str
    provider: str
    model_vendor: str
    base_url: str | None = None
    model: str
    enabled: bool
    supports_web_search: bool
    allow_external_network: bool
    json_mode: bool
    timeout_seconds: int
    max_tokens: int | None = None
    temperature: float
    daily_call_limit: int | None = None
    daily_token_limit: int | None = None
    prompt_template: AIPromptTemplateOut | None = None
    has_api_key: bool
    created_at: datetime
    updated_at: datetime


class AIProfileTestResult(BaseModel):
    success: bool
    status: str
    model: str
    latency_ms: int | None = None
    error_message: str | None = None


VulnerabilityAIEnrichmentLayer = Literal[
    "existing_data_extraction",
    "web_enrichment",
    "auto",
]
VulnerabilityAIEnrichmentStatus = Literal[
    "pending_review",
    "insufficient",
    "failed",
    "accepted",
    "rejected",
    "auto_accepted",
    "already_applied",
]


class VulnerabilityAIEnrichmentTriggerRequest(BaseModel):
    layer: VulnerabilityAIEnrichmentLayer = "existing_data_extraction"
    async_mode: bool = False
    allow_web_enrichment: bool = False
    profile_key: str | None = Field(default=None, min_length=1, max_length=64)
    force_refresh: bool = False


class VulnerabilityAIEnrichmentEvidence(BaseModel):
    field: str
    source_type: str | None = None
    source_url: str | None = None
    quote: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class AIFieldEvidenceStatusOut(BaseModel):
    field_name: str
    has_candidate: bool = False
    has_evidence: bool = False
    has_source_url: bool = False
    has_quote: bool = False


class AIEnrichmentQualityGateOut(BaseModel):
    quality_gate_status: str
    quality_gate_reasons: list[str] = Field(default_factory=list)
    quality_gate_warnings: list[str] = Field(default_factory=list)
    field_evidence_status: list[AIFieldEvidenceStatusOut] = Field(default_factory=list)
    source_url_count: int = 0
    candidate_field_count: int = 0
    confidence: float | None = None
    confidence_threshold: float | None = None
    auto_accept_allowed: bool = False
    manual_accept_risk_level: str = "none"


class VulnerabilityAIEnrichmentOut(BaseModel):
    id: str
    vulnerability_id: str
    layer: str
    source_mode: str
    profile_id: str | None = None
    model: str | None = None
    input_hash: str
    status: VulnerabilityAIEnrichmentStatus
    vendor: str | None = None
    product: str | None = None
    affected_versions: str | None = None
    fixed_versions: str | None = None
    remediation: str | None = None
    confidence: float | None = None
    evidence: list[VulnerabilityAIEnrichmentEvidence] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    raw_output: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    accepted_at: datetime | None = None
    accepted_by: str | None = None
    rejected_at: datetime | None = None
    rejected_by: str | None = None
    rejection_reason: str | None = None
    quality_gate: AIEnrichmentQualityGateOut | None = None
    created_at: datetime
    updated_at: datetime


class VulnerabilityAIEnrichmentRunResponse(BaseModel):
    async_queued: bool = False
    task_id: str | None = None
    enrichment: VulnerabilityAIEnrichmentOut | None = None


VulnerabilityAIEnrichmentAcceptField = Literal[
    "vendor",
    "product",
    "affected_versions",
    "fixed_versions",
    "remediation",
]


class VulnerabilityAIEnrichmentAcceptRequest(BaseModel):
    fields: list[VulnerabilityAIEnrichmentAcceptField] = Field(min_length=1)
    allow_overwrite: bool = False


class VulnerabilityAIEnrichmentAcceptResponse(BaseModel):
    enrichment: VulnerabilityAIEnrichmentOut
    updated_fields: dict[str, dict[str, Any]] = Field(default_factory=dict)
    skipped_fields: dict[str, str] = Field(default_factory=dict)
    matching_reevaluation_recommended: bool = False
    readiness_before: VulnerabilityReadinessOut | None = None
    readiness_after: VulnerabilityReadinessOut | None = None
    quality_gate: AIEnrichmentQualityGateOut | None = None


class VulnerabilityAIEnrichmentRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class VulnerabilityAIEnrichmentBatchFilters(BaseModel):
    match_readiness: Literal[
        "ready",
        "needs_enrichment",
        "needs_review",
        "not_matchable",
    ] | None = "needs_enrichment"
    missing_affected_versions: bool = True
    missing_fixed_versions: bool = False
    severity_labels: list[str] = Field(default_factory=list)
    kev_status: bool | None = None
    poc_status: bool | None = None
    wild_exploitation_status: bool | None = None


class VulnerabilityAIEnrichmentBatchRequest(BaseModel):
    filters: VulnerabilityAIEnrichmentBatchFilters = Field(
        default_factory=VulnerabilityAIEnrichmentBatchFilters
    )
    layer: Literal["existing_data_extraction", "web_enrichment", "auto"] = (
        "existing_data_extraction"
    )
    limit: int = Field(default=100, ge=1, le=500)
    allow_web_enrichment: bool = False
    async_mode: bool = True
    force_refresh: bool = False


class VulnerabilityAIEnrichmentBatchResponse(BaseModel):
    batch_run_id: str
    task_id: str | None = None
    status: str
    selected_count: int = 0
    skipped_count: int = 0
    message: str | None = None


class VulnerabilityAIEnrichmentBatchRunOut(BaseModel):
    id: str
    status: str
    trigger_type: str
    requested_by: str | None = None
    task_id: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    allow_web_enrichment: bool = False
    selected_count: int = 0
    processed_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    pending_review_count: int = 0
    insufficient_count: int = 0
    recent_error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class VulnerabilityAIEnrichmentBatchItemOut(BaseModel):
    vulnerability: VulnerabilityDetail
    enrichment: VulnerabilityAIEnrichmentOut | None = None
    result_status: str


class VulnerabilityAIEnrichmentBatchDetailOut(BaseModel):
    batch: VulnerabilityAIEnrichmentBatchRunOut
    items: list[VulnerabilityAIEnrichmentBatchItemOut] = Field(default_factory=list)


class AIEnrichmentProfileStats(BaseModel):
    profile_id: str | None = None
    profile_key: str | None = None
    model: str | None = None
    call_count: int = 0
    token_count: int = 0
    failed_count: int = 0


class AIEnrichmentStatsOut(BaseModel):
    today_call_count: int = 0
    today_token_count: int = 0
    layer1_success_rate: float | None = None
    layer2_success_rate: float | None = None
    pending_review_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    auto_accepted_count: int = 0
    failed_count: int = 0
    insufficient_count: int = 0
    average_confidence: float | None = None
    quality_gate_distribution: dict[str, int] = Field(default_factory=dict)
    quality_gate_reason_distribution: dict[str, int] = Field(default_factory=dict)
    by_profile: list[AIEnrichmentProfileStats] = Field(default_factory=list)
