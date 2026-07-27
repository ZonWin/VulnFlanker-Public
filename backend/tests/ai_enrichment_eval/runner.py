from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Vulnerability
from app.services.intel_ingestion import store_raw_event
from app.services.intel_normalization import normalize_raw_event
from app.services.vulnerability_ai_enrichment import (
    BASIC_EXTRACTION_PROFILE_KEY,
    enrich_vulnerability_from_existing_data,
)
from app.services.vulnerability_readiness import evaluate_vulnerability_readiness

from .dataset import AIEnrichmentEvalDataset, AIEnrichmentEvalSample


EVALUATED_FIELDS = (
    "vendor",
    "product",
    "affected_versions",
    "fixed_versions",
    "remediation",
)


@dataclass(slots=True)
class AIEnrichmentEvalSampleResult:
    sample_id: str
    canonical_id: str
    enrichment_status: str
    readiness_before: str
    readiness_after_without_accept: str
    quality_gate_status: str | None
    quality_gate_reasons: list[str] = field(default_factory=list)
    suggested_fields: dict[str, str | None] = field(default_factory=dict)
    expected_fields: dict[str, str | None] = field(default_factory=dict)
    field_matches: dict[str, bool | None] = field(default_factory=dict)
    error_message: str | None = None


@dataclass(slots=True)
class AIEnrichmentEvalReport:
    sample_count: int
    profile_key: str
    provider_mode: str
    field_accuracy: dict[str, float]
    field_match_counts: dict[str, int]
    field_expected_counts: dict[str, int]
    enrichment_status_distribution: dict[str, int]
    quality_gate_distribution: dict[str, int]
    quality_gate_reason_distribution: dict[str, int]
    readiness_before_distribution: dict[str, int]
    readiness_after_without_accept_distribution: dict[str, int]
    ready_conversion_observed_count: int
    results: list[AIEnrichmentEvalSampleResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "profile_key": self.profile_key,
            "provider_mode": self.provider_mode,
            "field_accuracy": self.field_accuracy,
            "field_match_counts": self.field_match_counts,
            "field_expected_counts": self.field_expected_counts,
            "enrichment_status_distribution": self.enrichment_status_distribution,
            "quality_gate_distribution": self.quality_gate_distribution,
            "quality_gate_reason_distribution": self.quality_gate_reason_distribution,
            "readiness_before_distribution": self.readiness_before_distribution,
            "readiness_after_without_accept_distribution": (
                self.readiness_after_without_accept_distribution
            ),
            "ready_conversion_observed_count": self.ready_conversion_observed_count,
            "results": [
                {
                    "sample_id": item.sample_id,
                    "canonical_id": item.canonical_id,
                    "enrichment_status": item.enrichment_status,
                    "readiness_before": item.readiness_before,
                    "readiness_after_without_accept": item.readiness_after_without_accept,
                    "quality_gate_status": item.quality_gate_status,
                    "quality_gate_reasons": item.quality_gate_reasons,
                    "suggested_fields": item.suggested_fields,
                    "expected_fields": item.expected_fields,
                    "field_matches": item.field_matches,
                    "error_message": item.error_message,
                }
                for item in self.results
            ],
        }


def run_ai_enrichment_eval(
    db: Session,
    dataset: AIEnrichmentEvalDataset,
    *,
    profile_key: str = BASIC_EXTRACTION_PROFILE_KEY,
    provider_mode: str = "fake",
    limit: int | None = None,
    sample_ids: set[str] | None = None,
) -> AIEnrichmentEvalReport:
    results: list[AIEnrichmentEvalSampleResult] = []
    selected_samples = dataset.samples
    if sample_ids is not None:
        selected_samples = [
            sample for sample in selected_samples if sample.sample_id in sample_ids
        ]
    if limit is not None:
        selected_samples = selected_samples[:limit]

    for sample in selected_samples:
        results.append(
            _run_sample(
                db,
                sample,
                profile_key=profile_key,
            )
        )

    return _build_report(
        results,
        profile_key=profile_key,
        provider_mode=provider_mode,
    )


def _run_sample(
    db: Session,
    sample: AIEnrichmentEvalSample,
    *,
    profile_key: str,
) -> AIEnrichmentEvalSampleResult:
    vulnerability = _normalize_sample(db, sample)
    readiness_before = evaluate_vulnerability_readiness(vulnerability)
    enrichment = enrich_vulnerability_from_existing_data(
        db,
        vulnerability.id,
        profile_key=profile_key,
    )
    db.refresh(vulnerability)
    readiness_after = evaluate_vulnerability_readiness(vulnerability)

    expected_fields = _expected_fields(sample)
    suggested_fields = {
        field_name: getattr(enrichment, field_name)
        for field_name in EVALUATED_FIELDS
    }
    field_matches = {
        field_name: _field_matches(
            suggested_fields[field_name],
            expected_fields[field_name],
            sample.expected,
            field_name,
        )
        for field_name in EVALUATED_FIELDS
    }

    return AIEnrichmentEvalSampleResult(
        sample_id=sample.sample_id,
        canonical_id=vulnerability.canonical_id,
        enrichment_status=enrichment.status,
        readiness_before=readiness_before.match_readiness,
        readiness_after_without_accept=readiness_after.match_readiness,
        quality_gate_status=(
            enrichment.quality_gate.quality_gate_status
            if enrichment.quality_gate
            else None
        ),
        quality_gate_reasons=(
            list(enrichment.quality_gate.quality_gate_reasons)
            if enrichment.quality_gate
            else []
        ),
        suggested_fields=suggested_fields,
        expected_fields=expected_fields,
        field_matches=field_matches,
        error_message=enrichment.error_message,
    )


def _normalize_sample(
    db: Session,
    sample: AIEnrichmentEvalSample,
) -> Vulnerability:
    raw_event_data = sample.raw_event
    raw_event, _created = store_raw_event(
        db,
        provider=raw_event_data["provider"],
        event_type=raw_event_data["event_type"],
        external_key=raw_event_data["external_key"],
        payload=raw_event_data["payload"],
        source_url=raw_event_data.get("source_url"),
    )
    result = normalize_raw_event(db, raw_event)
    if result.status != "processed" or not result.vulnerability_id:
        raise AssertionError(
            f"Sample {sample.sample_id} failed normalization: {result.status}"
        )
    vulnerability = db.get(Vulnerability, result.vulnerability_id)
    if vulnerability is None:
        raise AssertionError(f"Sample {sample.sample_id} vulnerability not found.")
    return vulnerability


def _expected_fields(sample: AIEnrichmentEvalSample) -> dict[str, str | None]:
    expected = sample.expected["expected"]
    return {field_name: expected[field_name] for field_name in EVALUATED_FIELDS}


def _field_matches(
    suggested: str | None,
    expected: str | None,
    expected_payload: dict[str, Any],
    field_name: str,
) -> bool | None:
    if expected is None:
        return None if suggested is None else False
    if field_name == "fixed_versions":
        if _normalize_fixed_version(suggested) == _normalize_fixed_version(expected):
            return True
    if field_name in {"affected_versions", "fixed_versions"}:
        if _normalize_version(suggested) == _normalize_version(expected):
            return True
    if _normalize(suggested) == _normalize(expected):
        return True
    if field_name == "product":
        aliases = expected_payload.get("acceptable", {}).get("product_aliases") or []
        return _normalize(suggested) in {_normalize(alias) for alias in aliases}
    if field_name == "affected_versions":
        natural = (
            expected_payload.get("acceptable", {})
            .get("affected_versions_natural_language")
            or []
        )
        return _normalize(suggested) in {_normalize(item) for item in natural}
    return False


def _build_report(
    results: list[AIEnrichmentEvalSampleResult],
    *,
    profile_key: str,
    provider_mode: str,
) -> AIEnrichmentEvalReport:
    field_expected_counts: Counter[str] = Counter()
    field_match_counts: Counter[str] = Counter()
    enrichment_status_distribution: Counter[str] = Counter()
    quality_gate_distribution: Counter[str] = Counter()
    quality_gate_reason_distribution: Counter[str] = Counter()
    readiness_before_distribution: Counter[str] = Counter()
    readiness_after_distribution: Counter[str] = Counter()
    ready_conversion_observed_count = 0

    for item in results:
        enrichment_status_distribution[item.enrichment_status] += 1
        if item.quality_gate_status:
            quality_gate_distribution[item.quality_gate_status] += 1
        quality_gate_reason_distribution.update(item.quality_gate_reasons)
        readiness_before_distribution[item.readiness_before] += 1
        readiness_after_distribution[item.readiness_after_without_accept] += 1
        if (
            item.readiness_before == "needs_enrichment"
            and item.readiness_after_without_accept == "ready"
        ):
            ready_conversion_observed_count += 1
        for field_name, matched in item.field_matches.items():
            if matched is None:
                continue
            field_expected_counts[field_name] += 1
            if matched:
                field_match_counts[field_name] += 1

    field_accuracy = {
        field_name: (
            field_match_counts[field_name] / field_expected_counts[field_name]
            if field_expected_counts[field_name]
            else 0.0
        )
        for field_name in EVALUATED_FIELDS
    }

    return AIEnrichmentEvalReport(
        sample_count=len(results),
        profile_key=profile_key,
        provider_mode=provider_mode,
        field_accuracy=field_accuracy,
        field_match_counts=dict(sorted(field_match_counts.items())),
        field_expected_counts=dict(sorted(field_expected_counts.items())),
        enrichment_status_distribution=dict(sorted(enrichment_status_distribution.items())),
        quality_gate_distribution=dict(sorted(quality_gate_distribution.items())),
        quality_gate_reason_distribution=dict(
            sorted(quality_gate_reason_distribution.items())
        ),
        readiness_before_distribution=dict(sorted(readiness_before_distribution.items())),
        readiness_after_without_accept_distribution=dict(
            sorted(readiness_after_distribution.items())
        ),
        ready_conversion_observed_count=ready_conversion_observed_count,
        results=results,
    )


def _normalize(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _normalize_version(value: str | None) -> str:
    normalized = _normalize(value)
    normalized = normalized.replace("、", ",")
    normalized = normalized.replace("||", ",")
    normalized = normalized.replace("，", ",")
    normalized = normalized.replace(" - ", "-")
    normalized = normalized.replace(" to ", "-")
    normalized = normalized.replace(" through ", "-")
    parts = [part.strip() for part in normalized.split(",")]
    return ",".join(part for part in parts if part)


def _normalize_fixed_version(value: str | None) -> str:
    normalized = _normalize_version(value)
    for prefix in (">=", "=>", "fixed in "):
        if normalized.startswith(prefix):
            return normalized.removeprefix(prefix).strip()
    return normalized
