from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_quality_chain_reports(
    report: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "quality_chain_report.json"
    markdown_path = output_dir / "quality_chain_report.md"

    with json_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(report, file, ensure_ascii=False, indent=2, default=str)
        file.write("\n")

    markdown_path.write_text(render_quality_chain_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def render_quality_chain_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Quality Chain Replay Report",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key in (
        "sample_count",
        "executed_count",
        "failed_count",
        "field_completeness_rate",
        "reference_coverage_rate",
        "needs_ai_enrichment_count",
        "needs_human_review_count",
        "source_conflict_count",
        "readiness_blocked_count",
        "match_status_accuracy",
        "false_positive_count",
        "false_negative_count",
        "needs_review_count",
        "needs_review_reason_coverage_rate",
        "kev_miss_count",
        "risk_priority_deviation_count",
    ):
        lines.append(f"| {key} | {_format_value(summary.get(key))} |")

    hard_gate_failures = report.get("hard_gate_failures") or []
    lines.extend(["", "## Hard Gate Failures", ""])
    if hard_gate_failures:
        for failure in hard_gate_failures:
            lines.append(f"- {failure}")
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Samples",
            "",
            "| Sample | Category | Status | Match accuracy | Notes |",
            "|---|---|---|---:|---|",
        ]
    )
    for sample in report.get("samples", []):
        sample_summary = sample.get("summary", {})
        notes = "; ".join(sample.get("issues") or []) or "-"
        lines.append(
            "| "
            f"{sample.get('id')} | "
            f"{sample.get('category')} | "
            f"{sample.get('status')} | "
            f"{_format_value(sample_summary.get('match_status_accuracy'))} | "
            f"{notes} |"
        )

    lines.extend(["", "## needs_review", ""])
    review_rows = []
    for sample in report.get("samples", []):
        for match in sample.get("matches", []):
            if match.get("actual_status") == "needs_review":
                review_rows.append(
                    (
                        sample.get("id"),
                        match.get("agent_id"),
                        match.get("reason") or "-",
                    )
                )
    if review_rows:
        lines.extend(["| Sample | Agent | Reason |", "|---|---|---|"])
        for sample_id, agent_id, reason in review_rows:
            lines.append(f"| {sample_id} | {agent_id} | {reason} |")
    else:
        lines.append("No needs_review results.")

    blocked_rows = []
    for sample in report.get("samples", []):
        for match in sample.get("matches", []):
            if match.get("actual_status") == "blocked_by_readiness":
                readiness = match.get("readiness") or {}
                blocked_rows.append(
                    (
                        sample.get("id"),
                        match.get("agent_id"),
                        readiness.get("match_readiness") or "-",
                        ", ".join(readiness.get("reasons") or []) or "-",
                    )
                )
    lines.extend(["", "## Readiness Blocks", ""])
    if blocked_rows:
        lines.extend(["| Sample | Agent | Readiness | Reasons |", "|---|---|---|---|"])
        for sample_id, agent_id, readiness, reasons in blocked_rows:
            lines.append(f"| {sample_id} | {agent_id} | {readiness} | {reasons} |")
    else:
        lines.append("No readiness blocks.")

    readiness_distribution = summary.get("readiness_distribution") or {}
    lines.extend(["", "## Readiness Distribution", ""])
    if readiness_distribution:
        lines.extend(["| Status | Count |", "|---|---:|"])
        for status, count in readiness_distribution.items():
            lines.append(f"| {status} | {count} |")
    else:
        lines.append("No readiness data.")

    issue_distribution = summary.get("issue_code_distribution") or {}
    lines.extend(["", "## Quality Issues", ""])
    if issue_distribution:
        lines.extend(["| Issue | Count |", "|---|---:|"])
        for issue_code, count in issue_distribution.items():
            lines.append(f"| {issue_code} | {count} |")
    else:
        lines.append("No quality issues.")

    lines.extend(["", "## Matching By Category", ""])
    _append_metric_table(lines, summary.get("category_metrics") or {})

    lines.extend(["", "## Matching By Label", ""])
    _append_metric_table(lines, summary.get("label_metrics") or {})

    lines.extend(["", "## Status Confusion Matrix", ""])
    _append_nested_count_table(
        lines,
        summary.get("status_confusion_matrix") or {},
        left_header="Expected",
        right_header="Actual",
    )

    risk_queue_metrics = summary.get("risk_queue_entry_metrics") or {}
    lines.extend(["", "## Risk Queue Entry", ""])
    if risk_queue_metrics:
        lines.extend(["| Metric | Value |", "|---|---:|"])
        for key, value in risk_queue_metrics.items():
            if key == "confusion":
                continue
            lines.append(f"| {key} | {_format_value(value)} |")
        confusion = risk_queue_metrics.get("confusion") or {}
        if confusion:
            lines.extend(["", "| Bucket | Count |", "|---|---:|"])
            for key, value in confusion.items():
                lines.append(f"| {key} | {value} |")
    else:
        lines.append("No risk queue data.")

    lines.extend(["", "## Rule Status Distribution", ""])
    _append_nested_count_table(
        lines,
        summary.get("rule_status_distribution") or {},
        left_header="Rule",
        right_header="Status",
    )

    reason_code_distribution = summary.get("rule_reason_code_distribution") or {}
    lines.extend(["", "## Rule Reason Codes", ""])
    if reason_code_distribution:
        lines.extend(["| Reason code | Count |", "|---|---:|"])
        for reason_code, count in reason_code_distribution.items():
            lines.append(f"| {reason_code} | {count} |")
    else:
        lines.append("No rule reason code data.")

    lines.extend(["", "## Evidence Type Coverage", ""])
    evidence_coverage = summary.get("evidence_type_coverage") or {}
    if evidence_coverage:
        lines.extend(
            [
                "| Evidence type | Expected | Present | Coverage |",
                "|---|---:|---:|---:|",
            ]
        )
        for evidence_type, metrics in evidence_coverage.items():
            lines.append(
                "| "
                f"{evidence_type} | "
                f"{metrics.get('expected_count')} | "
                f"{metrics.get('present_count')} | "
                f"{_format_value(metrics.get('coverage_rate'))} |"
            )
    else:
        lines.append("No expected evidence types.")

    return "\n".join(lines) + "\n"


def _append_metric_table(
    lines: list[str],
    metrics_by_name: dict[str, dict[str, object]],
) -> None:
    if not metrics_by_name:
        lines.append("No data.")
        return
    lines.extend(
        [
            "| Name | Samples | Matches | Accuracy | FP | FN | needs_review | Risk queue |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, metrics in metrics_by_name.items():
        lines.append(
            "| "
            f"{name} | "
            f"{metrics.get('sample_count')} | "
            f"{metrics.get('expected_match_count')} | "
            f"{_format_value(metrics.get('match_status_accuracy'))} | "
            f"{metrics.get('false_positive_count')} | "
            f"{metrics.get('false_negative_count')} | "
            f"{metrics.get('needs_review_count')} | "
            f"{metrics.get('risk_queue_entry_count')} |"
        )


def _append_nested_count_table(
    lines: list[str],
    matrix: dict[str, dict[str, int]],
    *,
    left_header: str,
    right_header: str,
) -> None:
    if not matrix:
        lines.append("No data.")
        return
    lines.extend(
        [
            f"| {left_header} | {right_header} | Count |",
            "|---|---|---:|",
        ]
    )
    for left, right_counts in matrix.items():
        for right, count in right_counts.items():
            lines.append(f"| {left} | {right} | {count} |")


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2%}" if 0 <= value <= 1 else f"{value:.2f}"
    if value is None:
        return "-"
    return str(value)
