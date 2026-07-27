from __future__ import annotations

import os
from pathlib import Path

from quality_chain.baseline import load_baseline_report
from quality_chain.loader import load_quality_chain_dataset
from quality_chain.reporter import write_quality_chain_reports
from quality_chain.runner import run_quality_chain_replay


def test_quality_chain_manifest_schema_is_valid() -> None:
    dataset = load_quality_chain_dataset()

    assert dataset.schema_version == "quality-chain-fixture-v1"
    assert dataset.dataset_version
    assert len(dataset.enabled_samples) == 30


def test_quality_chain_replay_generates_report(client, db_session, tmp_path) -> None:
    dataset = load_quality_chain_dataset()
    baseline_report = load_baseline_report(
        dataset.root / "baselines" / "quality_chain_report.baseline.json"
    )

    report = run_quality_chain_replay(
        client=client,
        db_session=db_session,
        dataset=dataset,
        baseline_report=baseline_report,
    )
    output_dir = Path(os.environ.get("QUALITY_CHAIN_REPORT_DIR") or tmp_path)
    json_path, markdown_path = write_quality_chain_reports(report, output_dir)

    assert report["hard_gate_passed"] is True
    assert report["summary"]["sample_count"] == len(dataset.enabled_samples)
    assert report["summary"]["failed_count"] == 0
    assert report["summary"]["match_status_accuracy"] == 1.0
    assert report["summary"]["false_positive_count"] == 0
    assert report["summary"]["false_negative_count"] == 0
    assert report["summary"]["needs_review_reason_coverage_rate"] == 1.0
    assert report["summary"]["risk_priority_deviation_count"] == 0
    assert "issue_code_distribution" in report["summary"]
    assert "needs_ai_enrichment_count" in report["summary"]
    assert "needs_human_review_count" in report["summary"]
    assert "source_conflict_count" in report["summary"]
    assert report["summary"]["readiness_blocked_count"] == 2
    assert "readiness_distribution" in report["summary"]
    assert "readiness_reason_distribution" in report["summary"]
    assert "category_metrics" in report["summary"]
    assert report["summary"]["category_metrics"]["kev"]["match_status_accuracy"] == 1.0
    assert "label_metrics" in report["summary"]
    assert report["summary"]["label_metrics"]["kev"]["false_negative_count"] == 0
    assert report["summary"]["expected_status_distribution"]["affected"] > 0
    assert report["summary"]["actual_status_distribution"]["affected"] > 0
    assert report["summary"]["status_confusion_matrix"]["affected"]["affected"] > 0
    assert report["summary"]["risk_queue_entry_metrics"]["mismatch_count"] == 0
    assert report["summary"]["evidence_type_coverage"]["product_match"][
        "coverage_rate"
    ] == 1.0
    assert "product_rule" in report["summary"]["rule_status_distribution"]
    assert report["summary"]["rule_reason_code_distribution"]
    assert report["summary"]["needs_review_reason_distribution"]
    assert report["summary"]["confidence_summary_by_status"]["affected"]["count"] > 0
    assert any(
        match.get("rule_trace")
        for sample in report["samples"]
        for match in sample["matches"]
        if match["actual_status"] != "blocked_by_readiness"
    )
    assert {sample["regression"]["status"] for sample in report["samples"]} == {
        "unchanged"
    }
    assert json_path.exists()
    assert markdown_path.exists()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Quality Chain Replay Report" in markdown
    assert "## Matching By Category" in markdown
    assert "## Status Confusion Matrix" in markdown
    assert "## Rule Status Distribution" in markdown
    assert "## Rule Reason Codes" in markdown
    assert "## Evidence Type Coverage" in markdown
