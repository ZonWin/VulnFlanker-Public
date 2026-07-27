from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_baseline_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Quality-chain baseline must be a JSON object: {path}")
    return data


def compare_with_baseline(
    current_report: dict[str, Any],
    baseline_report: dict[str, Any] | None,
) -> dict[str, dict[str, object]]:
    current_samples = {
        sample["id"]: sample
        for sample in current_report.get("samples", [])
        if isinstance(sample, dict) and sample.get("id")
    }
    if not baseline_report:
        return {
            sample_id: {"status": "new", "notes": []}
            for sample_id in current_samples
        }

    baseline_samples = {
        sample["id"]: sample
        for sample in baseline_report.get("samples", [])
        if isinstance(sample, dict) and sample.get("id")
    }
    comparison: dict[str, dict[str, object]] = {}
    for sample_id, current in current_samples.items():
        previous = baseline_samples.get(sample_id)
        if previous is None:
            comparison[sample_id] = {"status": "new", "notes": []}
            continue
        notes = _sample_regression_notes(previous, current)
        comparison[sample_id] = {
            "status": "regressed" if notes else "unchanged",
            "notes": notes,
        }
    return comparison


def _sample_regression_notes(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    previous_matches = _match_map(previous)
    current_matches = _match_map(current)
    for agent_id, previous_match in previous_matches.items():
        current_match = current_matches.get(agent_id)
        if current_match is None:
            notes.append(f"Match for {agent_id} disappeared.")
            continue
        if previous_match.get("actual_status") != current_match.get("actual_status"):
            notes.append(
                "Match status changed for "
                f"{agent_id}: {previous_match.get('actual_status')} -> "
                f"{current_match.get('actual_status')}."
            )
        if previous_match.get("actual_risk_priority") != current_match.get(
            "actual_risk_priority"
        ):
            notes.append(
                "Risk priority changed for "
                f"{agent_id}: {previous_match.get('actual_risk_priority')} -> "
                f"{current_match.get('actual_risk_priority')}."
            )
    return notes


def _match_map(sample: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["agent_id"]: item
        for item in sample.get("matches", [])
        if isinstance(item, dict) and item.get("agent_id")
    }
