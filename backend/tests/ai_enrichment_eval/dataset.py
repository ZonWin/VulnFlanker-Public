from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
EVAL_ROOT = FIXTURES_ROOT / "public_ai_enrichment_eval"
MANIFEST_FILE = EVAL_ROOT / "manifest.json"


@dataclass(slots=True)
class AIEnrichmentEvalSample:
    sample_id: str
    source: str
    title: str
    raw_event_path: Path
    sample_path: Path
    expected_path: Path
    raw_event: dict[str, Any]
    sample: dict[str, Any]
    expected: dict[str, Any]


@dataclass(slots=True)
class AIEnrichmentEvalDataset:
    schema_version: str
    stage: str
    root: Path
    samples: list[AIEnrichmentEvalSample]


def load_ai_enrichment_eval_dataset(
    manifest_path: Path | None = None,
) -> AIEnrichmentEvalDataset:
    manifest_path = manifest_path or MANIFEST_FILE
    root = manifest_path.parent
    manifest = _load_json(manifest_path)
    samples: list[AIEnrichmentEvalSample] = []
    seen_ids: set[str] = set()

    for item in manifest["samples"]:
        sample_id = _required_string(item, "sample_id")
        if sample_id in seen_ids:
            raise ValueError(f"Duplicate AI enrichment eval sample id: {sample_id}")
        seen_ids.add(sample_id)

        sample_path = root / "samples" / f"{sample_id}.json"
        expected_path = root / item["expected_ref"]
        raw_event_path = FIXTURES_ROOT / item["raw_event_ref"]
        sample = _load_json(sample_path)
        expected = _load_json(expected_path)
        raw_event = _load_json(raw_event_path)
        _validate_sample(sample_id, item, sample, expected, raw_event)
        samples.append(
            AIEnrichmentEvalSample(
                sample_id=sample_id,
                source=_required_string(item, "source"),
                title=_required_string(item, "title"),
                raw_event_path=raw_event_path,
                sample_path=sample_path,
                expected_path=expected_path,
                raw_event=raw_event,
                sample=sample,
                expected=expected,
            )
        )

    return AIEnrichmentEvalDataset(
        schema_version=_required_string(manifest, "schema_version"),
        stage=_required_string(manifest, "stage"),
        root=root,
        samples=samples,
    )


def _validate_sample(
    sample_id: str,
    item: dict[str, Any],
    sample: dict[str, Any],
    expected: dict[str, Any],
    raw_event: dict[str, Any],
) -> None:
    if sample.get("sample_id") != sample_id:
        raise ValueError(f"Sample {sample_id} sample_id mismatch.")
    if sample.get("raw_event_ref") != item.get("raw_event_ref"):
        raise ValueError(f"Sample {sample_id} raw_event_ref mismatch.")
    if expected.get("sample_id") != sample_id:
        raise ValueError(f"Sample {sample_id} expected.sample_id mismatch.")
    if raw_event.get("provider") != "watchvuln":
        raise ValueError(f"Sample {sample_id} raw event must use watchvuln provider.")
    if raw_event.get("event_type") != "watchvuln-vulninfo":
        raise ValueError(f"Sample {sample_id} raw event type mismatch.")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"AI enrichment eval fixture not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"AI enrichment eval fixture must be a JSON object: {path}")
    return data


def _required_string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required string field {field_name}.")
    return value
