from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Asset, MatchResult, Vulnerability, VulnerabilitySource
from app.services.intel_ingestion import store_raw_event
from app.services.intel_normalization import normalize_raw_event
from app.services.intel_tracking import _quality_for_vulnerability
from app.services.matching import VulnerabilityNotReadyForMatching, evaluate_matches
from app.services.vulnerability_readiness import evaluate_vulnerability_readiness

from .baseline import compare_with_baseline
from .loader import QualityChainDataset, QualityChainSample


RISK_PRIORITY_ORDER = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def run_quality_chain_replay(
    *,
    client: TestClient,
    db_session: Session,
    dataset: QualityChainDataset,
    baseline_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hard_gate_failures: list[str] = []
    sample_reports = [
        _run_sample(client, db_session, sample, hard_gate_failures)
        for sample in dataset.enabled_samples
    ]
    report = {
        "schema_version": "quality-chain-report-v1",
        "dataset_version": dataset.dataset_version,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "summary": _build_summary(sample_reports),
        "hard_gate_passed": not hard_gate_failures,
        "hard_gate_failures": hard_gate_failures,
        "samples": sample_reports,
    }
    comparison = compare_with_baseline(report, baseline_report)
    for sample in sample_reports:
        sample["regression"] = comparison.get(sample["id"], {"status": "new", "notes": []})
    return report


def _run_sample(
    client: TestClient,
    db_session: Session,
    sample: QualityChainSample,
    hard_gate_failures: list[str],
) -> dict[str, Any]:
    issues: list[str] = []
    expected_vulnerability = sample.expected["expected_vulnerability"]
    quality_expectations = sample.expected.get("quality_expectations") or {}
    canonical_id = expected_vulnerability["canonical_id"]

    raw_event, _ = store_raw_event(
        db_session,
        provider=sample.raw_event["provider"],
        event_type=sample.raw_event["event_type"],
        external_key=sample.raw_event["external_key"],
        payload=sample.raw_event["payload"],
        source_url=sample.raw_event.get("source_url"),
    )
    normalization_result = normalize_raw_event(db_session, raw_event)
    if (
        quality_expectations.get("normalization_must_succeed", True)
        and normalization_result.status != "processed"
    ):
        hard_gate_failures.append(
            f"{sample.id}: normalization expected processed, got {normalization_result.status}."
        )

    vulnerability = db_session.scalar(
        select(Vulnerability)
        .options(selectinload(Vulnerability.sources))
        .where(Vulnerability.canonical_id == normalization_result.canonical_id)
    )
    if vulnerability is None:
        hard_gate_failures.append(f"{sample.id}: normalized vulnerability not found.")
        return _failed_sample_report(sample, issues)

    if (
        quality_expectations.get("canonical_id_must_not_drift", True)
        and vulnerability.canonical_id != canonical_id
    ):
        hard_gate_failures.append(
            f"{sample.id}: canonical id drifted from {canonical_id} to {vulnerability.canonical_id}."
        )

    normalization_report = _build_normalization_report(
        vulnerability,
        expected_vulnerability,
    )
    readiness_report = normalization_report["readiness"]
    _compare_vulnerability_fields(
        sample.id,
        vulnerability,
        expected_vulnerability,
        issues,
    )

    for asset in sample.assets:
        response = client.post("/api/v1/agents/snapshots", json=asset)
        if response.status_code != 202:
            hard_gate_failures.append(
                f"{sample.id}: asset {asset.get('agent_id')} snapshot failed with "
                f"{response.status_code}: {response.text}"
            )

    readiness_block = None
    try:
        evaluate_matches(db_session, vulnerability_id=vulnerability.canonical_id)
    except VulnerabilityNotReadyForMatching as exc:
        readiness_block = exc.readiness

    match_reports = []
    for expected_match in sample.expected["expected_matches"]:
        match_report = _build_match_report(
            db_session=db_session,
            sample_id=sample.id,
            canonical_id=vulnerability.canonical_id,
            expected=expected_match,
            quality_expectations=quality_expectations,
            readiness_block=readiness_block,
            hard_gate_failures=hard_gate_failures,
            issues=issues,
        )
        match_reports.append(match_report)

    sample_summary = _build_sample_summary(normalization_report, match_reports)
    status = "passed" if not issues else "failed"
    return {
        "id": sample.id,
        "category": sample.category,
        "labels": sample.labels,
        "status": status,
        "issues": issues,
        "normalization": normalization_report,
        "readiness": readiness_report,
        "matches": match_reports,
        "summary": sample_summary,
    }


def _failed_sample_report(
    sample: QualityChainSample,
    issues: list[str],
) -> dict[str, Any]:
    return {
        "id": sample.id,
        "category": sample.category,
        "labels": sample.labels,
        "status": "failed",
        "issues": issues or ["Sample replay failed before comparison."],
        "normalization": {
            "field_completeness_rate": 0.0,
            "missing_fields": [],
            "quality_issue_codes": [],
            "needs_ai_enrichment": False,
            "needs_human_review": False,
            "source_conflict_count": 0,
            "conflict_fields": [],
            "reference_coverage_satisfied": False,
        },
        "matches": [],
        "summary": {
            "match_status_accuracy": 0.0,
        },
    }


def _build_normalization_report(
    vulnerability: Vulnerability,
    expected: dict[str, Any],
) -> dict[str, Any]:
    required_fields = expected.get("required_fields") or []
    missing_fields = [
        field_name
        for field_name in required_fields
        if not _present(getattr(vulnerability, field_name, None))
    ]
    sources = list(vulnerability.sources)
    references = [
        reference
        for source in sources
        for reference in (source.references_json or [])
    ]
    source_urls = [source.source_url for source in sources if source.source_url]
    required_reference_count = int(expected.get("required_references_min_count") or 0)
    present_required = len(required_fields) - len(missing_fields)
    completeness = (
        present_required / len(required_fields)
        if required_fields
        else 1.0
    )
    quality = _quality_for_vulnerability(vulnerability)
    readiness = evaluate_vulnerability_readiness(vulnerability)
    return {
        "expected_canonical_id": expected.get("canonical_id"),
        "actual_canonical_id": vulnerability.canonical_id,
        "field_completeness_rate": round(completeness, 4),
        "missing_fields": missing_fields,
        "quality_issue_codes": quality.issue_codes if quality else [],
        "needs_ai_enrichment": quality.needs_ai_enrichment if quality else False,
        "needs_human_review": quality.needs_human_review if quality else False,
        "source_conflict_count": quality.source_conflict_count if quality else 0,
        "conflict_fields": quality.conflict_fields if quality else [],
        "reference_count": len(references),
        "source_url_count": len(source_urls),
        "reference_coverage_satisfied": len(references) >= required_reference_count,
        "actual": {
            "vendor": vulnerability.vendor,
            "product": vulnerability.product,
            "kev_status": vulnerability.kev_status,
            "affected_versions": vulnerability.affected_versions,
            "fixed_versions": vulnerability.fixed_versions,
        },
        "readiness": {
            "information_completeness": readiness.information_completeness,
            "match_readiness": readiness.match_readiness,
            "reasons": readiness.reasons,
            "missing_fields": readiness.missing_fields,
            "evidence_score": readiness.evidence_score,
            "rule_version": readiness.rule_version,
        },
    }


def _compare_vulnerability_fields(
    sample_id: str,
    vulnerability: Vulnerability,
    expected: dict[str, Any],
    issues: list[str],
) -> None:
    for field_name in (
        "canonical_id",
        "vendor",
        "product",
        "kev_status",
        "affected_versions",
        "fixed_versions",
    ):
        if field_name not in expected:
            continue
        actual = getattr(vulnerability, field_name)
        if actual != expected[field_name]:
            issues.append(
                f"{sample_id}: expected vulnerability {field_name}={expected[field_name]!r}, "
                f"got {actual!r}."
            )


def _build_match_report(
    db_session: Session,
    sample_id: str,
    canonical_id: str,
    expected: dict[str, Any],
    quality_expectations: dict[str, Any],
    readiness_block,
    hard_gate_failures: list[str],
    issues: list[str],
) -> dict[str, Any]:
    agent_id = expected["agent_id"]
    match_result = db_session.scalar(
        select(MatchResult)
        .join(MatchResult.vulnerability)
        .join(MatchResult.asset)
        .options(selectinload(MatchResult.evidence))
        .where(
            Vulnerability.canonical_id == canonical_id,
            Asset.agent_id == agent_id,
        )
    )
    if match_result is None:
        expected_enters_risk_queue = _expected_risk_queue_entry(expected)
        if readiness_block is not None:
            actual_status = "blocked_by_readiness"
            status_matched = expected["status"] == actual_status
            if not status_matched:
                issues.append(
                    f"{sample_id}: {agent_id} expected status {expected['status']}, "
                    f"got {actual_status}."
                )
            return {
                "agent_id": agent_id,
                "expected_status": expected["status"],
                "actual_status": actual_status,
                "status_matched": status_matched,
                "readiness": {
                    "information_completeness": (
                        readiness_block.information_completeness
                    ),
                    "match_readiness": readiness_block.match_readiness,
                    "reasons": readiness_block.reasons,
                    "missing_fields": readiness_block.missing_fields,
                    "rule_version": readiness_block.rule_version,
                },
                "reason": "; ".join(readiness_block.reasons) or readiness_block.match_readiness,
                "expected_risk_priority": expected.get("risk_priority_one_of") or [],
                "actual_risk_priority": "none",
                "risk_priority_matched": True,
                "risk_score": 0.0,
                "confidence": 0.0,
                "review_reason_present": True,
                "evidence_types": [],
                "required_evidence_types": expected.get("required_evidence_types") or [],
                "required_evidence_missing": [],
                "expected_enters_risk_queue": expected_enters_risk_queue,
                "enters_risk_queue": False,
            }
        hard_gate_failures.append(f"{sample_id}: missing match result for {agent_id}.")
        return {
            "agent_id": agent_id,
            "expected_status": expected["status"],
            "actual_status": None,
            "status_matched": False,
            "required_evidence_types": expected.get("required_evidence_types") or [],
            "required_evidence_missing": expected.get("required_evidence_types") or [],
            "expected_enters_risk_queue": expected_enters_risk_queue,
        }

    evidence_types = {evidence.evidence_type for evidence in match_result.evidence}
    rule_trace = [
        _rule_trace_report(evidence.details_json or {})
        for evidence in match_result.evidence
        if evidence.evidence_type == "rule_trace"
    ]
    missing_evidence = [
        evidence_type
        for evidence_type in (expected.get("required_evidence_types") or [])
        if evidence_type not in evidence_types
    ]
    status_matched = match_result.status == expected["status"]
    if not status_matched:
        issues.append(
            f"{sample_id}: {agent_id} expected status {expected['status']}, "
            f"got {match_result.status}."
        )
    if missing_evidence:
        issues.append(
            f"{sample_id}: {agent_id} missing evidence types {missing_evidence}."
        )

    min_confidence = expected.get("min_confidence")
    max_confidence = expected.get("max_confidence")
    if min_confidence is not None and match_result.confidence < float(min_confidence):
        issues.append(
            f"{sample_id}: {agent_id} confidence {match_result.confidence} below {min_confidence}."
        )
    if max_confidence is not None and match_result.confidence > float(max_confidence):
        issues.append(
            f"{sample_id}: {agent_id} confidence {match_result.confidence} above {max_confidence}."
        )

    expected_priorities = expected.get("risk_priority_one_of") or []
    risk_priority_matched = (
        not expected_priorities or match_result.risk_priority in expected_priorities
    )
    if not risk_priority_matched:
        issues.append(
            f"{sample_id}: {agent_id} expected risk priority in {expected_priorities}, "
            f"got {match_result.risk_priority}."
        )

    should_enter_risk_queue = expected.get("should_enter_risk_queue")
    expected_enters_risk_queue = _expected_risk_queue_entry(expected)
    enters_risk_queue = match_result.status in {"affected", "needs_review", "verified"} and (
        match_result.risk_score > 0
    )
    if should_enter_risk_queue is not None and enters_risk_queue != bool(
        should_enter_risk_queue
    ):
        issues.append(
            f"{sample_id}: {agent_id} risk queue expectation {should_enter_risk_queue}, "
            f"got {enters_risk_queue}."
        )

    review_reason_present = _has_review_reason(match_result)
    if (
        quality_expectations.get("needs_review_requires_reason", True)
        and match_result.status == "needs_review"
        and not review_reason_present
    ):
        hard_gate_failures.append(
            f"{sample_id}: {agent_id} needs_review result has no readable reason."
        )

    return {
        "agent_id": agent_id,
        "expected_status": expected["status"],
        "actual_status": match_result.status,
        "status_matched": status_matched,
        "expected_risk_priority": expected_priorities,
        "actual_risk_priority": match_result.risk_priority,
        "risk_priority_matched": risk_priority_matched,
        "risk_score": match_result.risk_score,
        "confidence": match_result.confidence,
        "reason": match_result.match_reason,
        "review_reason_present": review_reason_present,
        "evidence_types": sorted(evidence_types),
        "required_evidence_types": expected.get("required_evidence_types") or [],
        "required_evidence_missing": missing_evidence,
        "expected_enters_risk_queue": expected_enters_risk_queue,
        "enters_risk_queue": enters_risk_queue,
        "rule_trace": rule_trace,
    }


def _build_sample_summary(
    normalization_report: dict[str, Any],
    matches: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_match_count = len(matches)
    matched_count = sum(1 for match in matches if match.get("status_matched"))
    return {
        "field_completeness_rate": normalization_report["field_completeness_rate"],
        "reference_coverage_satisfied": normalization_report[
            "reference_coverage_satisfied"
        ],
        "needs_ai_enrichment": normalization_report.get("needs_ai_enrichment", False),
        "needs_human_review": normalization_report.get("needs_human_review", False),
        "source_conflict_count": normalization_report.get("source_conflict_count", 0),
        "expected_match_count": expected_match_count,
        "match_status_accuracy": (
            matched_count / expected_match_count if expected_match_count else 1.0
        ),
    }


def _build_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [
        match
        for sample in samples
        for match in sample.get("matches", [])
    ]
    expected_match_count = len(matches)
    status_match_count = sum(1 for match in matches if match.get("status_matched"))
    needs_review_matches = [
        match for match in matches if match.get("actual_status") == "needs_review"
    ]
    field_rates = [
        sample.get("normalization", {}).get("field_completeness_rate", 0.0)
        for sample in samples
    ]
    reference_satisfied = [
        sample.get("normalization", {}).get("reference_coverage_satisfied", False)
        for sample in samples
    ]
    issue_code_counts: dict[str, int] = {}
    readiness_counts: dict[str, int] = {}
    readiness_reason_counts: dict[str, int] = {}
    for sample in samples:
        for issue_code in sample.get("normalization", {}).get("quality_issue_codes", []):
            issue_code_counts[issue_code] = issue_code_counts.get(issue_code, 0) + 1
        readiness = sample.get("readiness") or {}
        match_readiness = readiness.get("match_readiness")
        if match_readiness:
            readiness_counts[match_readiness] = readiness_counts.get(match_readiness, 0) + 1
        for reason in readiness.get("reasons") or []:
            readiness_reason_counts[reason] = readiness_reason_counts.get(reason, 0) + 1
    return {
        "sample_count": len(samples),
        "executed_count": len(samples),
        "failed_count": sum(1 for sample in samples if sample.get("status") != "passed"),
        "field_completeness_rate": _average(field_rates),
        "reference_coverage_rate": _average([1.0 if item else 0.0 for item in reference_satisfied]),
        "needs_ai_enrichment_count": sum(
            1
            for sample in samples
            if sample.get("normalization", {}).get("needs_ai_enrichment")
        ),
        "needs_human_review_count": sum(
            1
            for sample in samples
            if sample.get("normalization", {}).get("needs_human_review")
        ),
        "source_conflict_count": sum(
            int(sample.get("normalization", {}).get("source_conflict_count") or 0)
            for sample in samples
        ),
        "issue_code_distribution": dict(sorted(issue_code_counts.items())),
        "readiness_distribution": dict(sorted(readiness_counts.items())),
        "readiness_reason_distribution": dict(sorted(readiness_reason_counts.items())),
        "readiness_blocked_count": sum(
            1 for match in matches if match.get("actual_status") == "blocked_by_readiness"
        ),
        "expected_match_count": expected_match_count,
        "match_status_accuracy": (
            status_match_count / expected_match_count if expected_match_count else 1.0
        ),
        "false_positive_count": sum(
            1
            for match in matches
            if match.get("expected_status") == "not_affected"
            and match.get("actual_status") in {"affected", "verified"}
        ),
        "false_negative_count": sum(
            1
            for match in matches
            if match.get("expected_status") == "affected"
            and match.get("actual_status") == "not_affected"
        ),
        "needs_review_count": len(needs_review_matches),
        "needs_review_reason_coverage_rate": (
            sum(1 for match in needs_review_matches if match.get("review_reason_present"))
            / len(needs_review_matches)
            if needs_review_matches
            else 1.0
        ),
        "kev_miss_count": 0,
        "risk_priority_deviation_count": sum(
            1 for match in matches if not match.get("risk_priority_matched", True)
        ),
        "category_metrics": _group_metrics(samples, group_key="category"),
        "label_metrics": _label_metrics(samples),
        "expected_status_distribution": _status_distribution(
            matches,
            status_key="expected_status",
        ),
        "actual_status_distribution": _status_distribution(
            matches,
            status_key="actual_status",
        ),
        "status_confusion_matrix": _status_confusion_matrix(matches),
        "risk_queue_entry_metrics": _risk_queue_entry_metrics(matches),
        "evidence_type_distribution": _evidence_type_distribution(matches),
        "evidence_type_coverage": _evidence_type_coverage(matches),
        "rule_status_distribution": _rule_status_distribution(matches),
        "rule_reason_code_distribution": _rule_reason_code_distribution(matches),
        "needs_review_reason_distribution": _needs_review_reason_distribution(
            needs_review_matches,
        ),
        "confidence_summary_by_status": _confidence_summary_by_status(matches),
    }


def _rule_trace_report(details: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_name": details.get("rule_name"),
        "status": details.get("status"),
        "confidence": details.get("confidence"),
        "reason": details.get("reason"),
        "reason_code": details.get("reason_code"),
        "uncertain_reason": details.get("uncertain_reason"),
        "executed": details.get("executed"),
        "evidence_count": details.get("evidence_count"),
    }


def _group_metrics(
    samples: list[dict[str, Any]],
    *,
    group_key: str,
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for sample in samples:
        group = str(sample.get(group_key) or "unknown")
        groups.setdefault(group, []).append(sample)
    return {
        group: _metrics_for_matches(
            [
                match
                for sample in grouped_samples
                for match in sample.get("matches", [])
            ],
            sample_count=len(grouped_samples),
        )
        for group, grouped_samples in sorted(groups.items())
    }


def _label_metrics(samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    labels: dict[str, list[dict[str, Any]]] = {}
    for sample in samples:
        for label in sample.get("labels") or []:
            labels.setdefault(str(label), []).append(sample)
    return {
        label: _metrics_for_matches(
            [
                match
                for sample in labeled_samples
                for match in sample.get("matches", [])
            ],
            sample_count=len(labeled_samples),
        )
        for label, labeled_samples in sorted(labels.items())
    }


def _metrics_for_matches(
    matches: list[dict[str, Any]],
    *,
    sample_count: int,
) -> dict[str, Any]:
    expected_match_count = len(matches)
    status_match_count = sum(1 for match in matches if match.get("status_matched"))
    needs_review_count = sum(
        1 for match in matches if match.get("actual_status") == "needs_review"
    )
    return {
        "sample_count": sample_count,
        "expected_match_count": expected_match_count,
        "status_match_count": status_match_count,
        "match_status_accuracy": (
            round(status_match_count / expected_match_count, 4)
            if expected_match_count
            else 1.0
        ),
        "false_positive_count": sum(
            1
            for match in matches
            if match.get("expected_status") == "not_affected"
            and match.get("actual_status") in {"affected", "verified"}
        ),
        "false_negative_count": sum(
            1
            for match in matches
            if match.get("expected_status") == "affected"
            and match.get("actual_status") == "not_affected"
        ),
        "needs_review_count": needs_review_count,
        "risk_queue_entry_count": sum(1 for match in matches if match.get("enters_risk_queue")),
        "risk_priority_deviation_count": sum(
            1 for match in matches if not match.get("risk_priority_matched", True)
        ),
    }


def _status_distribution(
    matches: list[dict[str, Any]],
    *,
    status_key: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in matches:
        status = str(match.get(status_key) or "none")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _status_confusion_matrix(matches: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for match in matches:
        expected = str(match.get("expected_status") or "none")
        actual = str(match.get("actual_status") or "none")
        matrix.setdefault(expected, {})
        matrix[expected][actual] = matrix[expected].get(actual, 0) + 1
    return {
        expected: dict(sorted(actual_counts.items()))
        for expected, actual_counts in sorted(matrix.items())
    }


def _risk_queue_entry_metrics(matches: list[dict[str, Any]]) -> dict[str, Any]:
    expected_known = [
        match for match in matches if match.get("expected_enters_risk_queue") is not None
    ]
    expected_true = [
        match for match in expected_known if _expected_risk_queue_entry(match)
    ]
    expected_false = [
        match for match in expected_known if not _expected_risk_queue_entry(match)
    ]
    actual_true = [match for match in expected_known if match.get("enters_risk_queue")]
    matched = [
        match
        for match in expected_known
        if _expected_risk_queue_entry(match) == bool(match.get("enters_risk_queue"))
    ]
    return {
        "expected_entry_count": len(expected_true),
        "expected_non_entry_count": len(expected_false),
        "actual_entry_count": len(actual_true),
        "matched_count": len(matched),
        "mismatch_count": len(expected_known) - len(matched),
        "accuracy": (
            round(len(matched) / len(expected_known), 4)
            if expected_known
            else 1.0
        ),
        "confusion": {
            "expected_true_actual_true": sum(
                1
                for match in expected_known
                if _expected_risk_queue_entry(match)
                and bool(match.get("enters_risk_queue"))
            ),
            "expected_true_actual_false": sum(
                1
                for match in expected_known
                if _expected_risk_queue_entry(match)
                and not bool(match.get("enters_risk_queue"))
            ),
            "expected_false_actual_true": sum(
                1
                for match in expected_known
                if not _expected_risk_queue_entry(match)
                and bool(match.get("enters_risk_queue"))
            ),
            "expected_false_actual_false": sum(
                1
                for match in expected_known
                if not _expected_risk_queue_entry(match)
                and not bool(match.get("enters_risk_queue"))
            ),
        },
    }


def _expected_risk_queue_entry(match: dict[str, Any]) -> bool:
    explicit = match.get("should_enter_risk_queue")
    if explicit is None:
        explicit = match.get("expected_enters_risk_queue")
    if explicit is not None:
        return bool(explicit)
    return match.get("expected_status") in {"affected", "needs_review", "verified"}


def _evidence_type_distribution(matches: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in matches:
        for evidence_type in match.get("evidence_types") or []:
            evidence_type = str(evidence_type)
            counts[evidence_type] = counts.get(evidence_type, 0) + 1
    return dict(sorted(counts.items()))


def _evidence_type_coverage(matches: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    expected_counts: dict[str, int] = {}
    present_counts: dict[str, int] = {}
    for match in matches:
        present = set(match.get("evidence_types") or [])
        required = set(match.get("required_evidence_types") or [])
        for evidence_type in required:
            evidence_type = str(evidence_type)
            expected_counts[evidence_type] = expected_counts.get(evidence_type, 0) + 1
            if evidence_type in present:
                present_counts[evidence_type] = present_counts.get(evidence_type, 0) + 1

    return {
        evidence_type: {
            "expected_count": expected_count,
            "present_count": present_counts.get(evidence_type, 0),
            "coverage_rate": (
                round(present_counts.get(evidence_type, 0) / expected_count, 4)
                if expected_count
                else 1.0
            ),
        }
        for evidence_type, expected_count in sorted(expected_counts.items())
    }


def _rule_status_distribution(matches: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    distribution: dict[str, dict[str, int]] = {}
    for match in matches:
        for trace in match.get("rule_trace") or []:
            rule_name = str(trace.get("rule_name") or "unknown")
            status = str(trace.get("status") or "unknown")
            distribution.setdefault(rule_name, {})
            distribution[rule_name][status] = distribution[rule_name].get(status, 0) + 1
    return {
        rule_name: dict(sorted(status_counts.items()))
        for rule_name, status_counts in sorted(distribution.items())
    }


def _rule_reason_code_distribution(matches: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in matches:
        for trace in match.get("rule_trace") or []:
            reason_code = str(trace.get("reason_code") or "missing_reason_code")
            counts[reason_code] = counts.get(reason_code, 0) + 1
    return dict(sorted(counts.items()))


def _needs_review_reason_distribution(
    needs_review_matches: list[dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in needs_review_matches:
        reason = str(match.get("reason") or "missing_reason")
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _confidence_summary_by_status(
    matches: list[dict[str, Any]],
) -> dict[str, dict[str, float | int]]:
    values_by_status: dict[str, list[float]] = {}
    for match in matches:
        confidence = match.get("confidence")
        if confidence is None:
            continue
        status = str(match.get("actual_status") or "none")
        values_by_status.setdefault(status, []).append(float(confidence))
    return {
        status: {
            "count": len(values),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "avg": _average(values),
        }
        for status, values in sorted(values_by_status.items())
        if values
    }


def _has_review_reason(match_result: MatchResult) -> bool:
    if _present(match_result.match_reason):
        return True
    for evidence in match_result.evidence:
        if _present(evidence.summary):
            return True
        details = evidence.details_json or {}
        if _present(details.get("comparison_reason")):
            return True
    return False


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | set | dict):
        return bool(value)
    return True


def _average(values: list[float]) -> float:
    if not values:
        return 1.0
    return round(sum(values) / len(values), 4)
