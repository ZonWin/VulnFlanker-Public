from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ai_enrichment_eval.dataset import load_ai_enrichment_eval_dataset
from ai_enrichment_eval.runner import run_ai_enrichment_eval


FIXTURES_ROOT = Path(__file__).parent / "fixtures"
EVAL_ROOT = FIXTURES_ROOT / "public_ai_enrichment_eval"
MANIFEST_FILE = EVAL_ROOT / "manifest.json"


def test_ai_enrichment_eval_manifest_and_expected_files_are_valid() -> None:
    manifest = _load_json(MANIFEST_FILE)

    assert manifest["schema_version"] == "ai-enrichment-eval-v1"
    assert manifest["stage"] == "public-synthetic"
    assert manifest["sample_count"] == 2

    samples = manifest["samples"]
    assert isinstance(samples, list)
    assert len(samples) == manifest["sample_count"]

    seen_ids: set[str] = set()
    source_counts: Counter[str] = Counter()
    non_cve_count = 0
    has_cve_count = 0
    for item in samples:
        sample_id = _required_string(item, "sample_id")
        assert sample_id not in seen_ids
        seen_ids.add(sample_id)

        sample = _load_json(EVAL_ROOT / "samples" / f"{sample_id}.json")
        expected = _load_json(EVAL_ROOT / item["expected_ref"])
        raw_event = _load_json(FIXTURES_ROOT / item["raw_event_ref"])

        assert sample["sample_id"] == sample_id
        assert sample["raw_event_ref"] == item["raw_event_ref"]
        assert expected["sample_id"] == sample_id
        assert raw_event["provider"] == "watchvuln"
        assert raw_event["event_type"] == "watchvuln-vulninfo"

        source_counts[item["source"]] += 1
        content = raw_event["payload"]["content"]
        if content.get("cve"):
            has_cve_count += 1
        else:
            non_cve_count += 1

        _validate_sample(sample_id, sample)
        _validate_expected(sample_id, expected)

    assert dict(sorted(source_counts.items())) == manifest["selection_summary"]["sources"]
    assert has_cve_count == manifest["selection_summary"]["has_cve_count"]
    assert non_cve_count == manifest["selection_summary"]["non_cve_count"]


def test_ai_enrichment_eval_runner_produces_fake_provider_baseline(
    db_session: Session,
) -> None:
    dataset = load_ai_enrichment_eval_dataset()

    report = run_ai_enrichment_eval(db_session, dataset, provider_mode="fake")

    assert report.sample_count == 2
    assert sum(report.enrichment_status_distribution.values()) == 2
    assert sum(report.quality_gate_distribution.values()) == 2
    assert sum(report.readiness_before_distribution.values()) == 2
    assert "product" in report.field_accuracy
    assert "affected_versions" in report.field_accuracy
    assert "fixed_versions" in report.field_accuracy
    assert report.field_expected_counts["product"] == 1
    assert report.ready_conversion_observed_count == 0
    assert len(report.to_dict()["results"]) == 2


def _validate_sample(sample_id: str, sample: dict[str, Any]) -> None:
    _required_string(sample, "raw_event_ref", sample_id=sample_id)
    _required_string(sample, "selection_reason", sample_id=sample_id)
    missing_fields = sample.get("missing_fields")
    focus = sample.get("evaluation_focus")
    assert isinstance(missing_fields, list) and missing_fields
    assert isinstance(focus, list) and focus
    assert all(isinstance(item, str) and item for item in missing_fields)
    assert all(isinstance(item, str) and item for item in focus)


def _validate_expected(sample_id: str, expected: dict[str, Any]) -> None:
    fields = expected.get("expected")
    acceptable = expected.get("acceptable")
    judgement = expected.get("judgement")
    assert isinstance(fields, dict)
    assert isinstance(acceptable, dict)
    assert isinstance(judgement, dict)

    for field_name in (
        "vendor",
        "product",
        "affected_versions",
        "fixed_versions",
        "remediation",
    ):
        assert field_name in fields
        assert fields[field_name] is None or isinstance(fields[field_name], str)

    assert isinstance(acceptable.get("product_aliases"), list)
    assert isinstance(acceptable.get("affected_versions_natural_language"), list)
    assert isinstance(judgement.get("allow_auto_accept"), bool)
    assert judgement.get("expected_readiness_after_accept") in {
        "ready",
        "needs_enrichment",
        "needs_review",
        "not_matchable",
    }
    assert judgement.get("expected_quality_gate_status") in {
        "passed",
        "needs_review",
        "failed",
        "not_applicable",
    }
    _required_string(judgement, "review_notes", sample_id=sample_id)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    assert isinstance(data, dict)
    return data


def _required_string(
    data: dict[str, Any],
    field_name: str,
    *,
    sample_id: str | None = None,
) -> str:
    value = data.get(field_name)
    prefix = f"Sample {sample_id} " if sample_id else ""
    assert isinstance(value, str) and value.strip(), (
        f"{prefix}missing required string field {field_name}."
    )
    return value
