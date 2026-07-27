from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "quality_chain"
MANIFEST_FILE = FIXTURE_ROOT / "manifest.json"


@dataclass(slots=True)
class QualityChainSample:
    id: str
    category: str
    enabled: bool
    labels: list[str]
    notes: str | None
    raw_event_path: Path
    asset_paths: list[Path]
    expected_path: Path
    raw_event: dict[str, Any]
    assets: list[dict[str, Any]]
    expected: dict[str, Any]


@dataclass(slots=True)
class QualityChainDataset:
    schema_version: str
    dataset_version: str
    description: str | None
    root: Path
    samples: list[QualityChainSample]

    @property
    def enabled_samples(self) -> list[QualityChainSample]:
        return [sample for sample in self.samples if sample.enabled]


def load_quality_chain_dataset(
    manifest_path: Path | None = None,
) -> QualityChainDataset:
    manifest_path = manifest_path or MANIFEST_FILE
    root = manifest_path.parent
    manifest = _load_json(manifest_path)
    _validate_manifest(manifest)

    seen_ids: set[str] = set()
    samples: list[QualityChainSample] = []
    for item in manifest["samples"]:
        sample_id = _required_string(item, "id")
        if sample_id in seen_ids:
            raise ValueError(f"Duplicate quality-chain sample id: {sample_id}")
        seen_ids.add(sample_id)

        raw_event_path = _resolve_fixture_path(root, item["raw_event"])
        asset_paths = [_resolve_fixture_path(root, path) for path in item["assets"]]
        expected_path = _resolve_fixture_path(root, item["expected"])
        raw_event = _load_json(raw_event_path)
        assets = [_load_json(path) for path in asset_paths]
        expected = _load_json(expected_path)
        _validate_raw_event(sample_id, raw_event)
        _validate_assets(sample_id, assets)
        _validate_expected(sample_id, expected)

        samples.append(
            QualityChainSample(
                id=sample_id,
                category=_required_string(item, "category"),
                enabled=bool(item["enabled"]),
                labels=list(item.get("labels") or []),
                notes=item.get("notes"),
                raw_event_path=raw_event_path,
                asset_paths=asset_paths,
                expected_path=expected_path,
                raw_event=raw_event,
                assets=assets,
                expected=expected,
            )
        )

    return QualityChainDataset(
        schema_version=_required_string(manifest, "schema_version"),
        dataset_version=_required_string(manifest, "dataset_version"),
        description=manifest.get("description"),
        root=root,
        samples=samples,
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Quality-chain fixture does not exist: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Quality-chain fixture must be a JSON object: {path}")
    return data


def _resolve_fixture_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    if root.resolve() not in path.parents and path != root.resolve():
        raise ValueError(f"Quality-chain fixture path escapes root: {relative_path}")
    if not path.exists():
        raise FileNotFoundError(f"Quality-chain fixture file not found: {path}")
    return path


def _validate_manifest(manifest: dict[str, Any]) -> None:
    _required_string(manifest, "schema_version")
    _required_string(manifest, "dataset_version")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("Quality-chain manifest must contain non-empty samples.")
    for item in samples:
        if not isinstance(item, dict):
            raise ValueError("Quality-chain sample entry must be an object.")
        for field_name in ("id", "category", "raw_event", "expected"):
            _required_string(item, field_name)
        if not isinstance(item.get("enabled"), bool):
            raise ValueError(f"Sample {item.get('id')} must define boolean enabled.")
        assets = item.get("assets")
        if not isinstance(assets, list) or not assets:
            raise ValueError(f"Sample {item.get('id')} must reference at least one asset.")
        if not all(isinstance(path, str) and path for path in assets):
            raise ValueError(f"Sample {item.get('id')} has invalid asset paths.")


def _validate_raw_event(sample_id: str, raw_event: dict[str, Any]) -> None:
    for field_name in ("provider", "event_type", "external_key"):
        _required_string(raw_event, field_name, sample_id=sample_id)
    payload = raw_event.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"Sample {sample_id} raw_event.payload must be an object.")


def _validate_assets(sample_id: str, assets: list[dict[str, Any]]) -> None:
    for asset in assets:
        for field_name in ("agent_id", "hostname", "components", "exposures"):
            if field_name not in asset:
                raise ValueError(f"Sample {sample_id} asset missing {field_name}.")
        if not isinstance(asset["components"], list):
            raise ValueError(f"Sample {sample_id} asset.components must be a list.")
        if not isinstance(asset["exposures"], list):
            raise ValueError(f"Sample {sample_id} asset.exposures must be a list.")


def _validate_expected(sample_id: str, expected: dict[str, Any]) -> None:
    if expected.get("sample_id") != sample_id:
        raise ValueError(f"Sample {sample_id} expected.sample_id mismatch.")
    vulnerability = expected.get("expected_vulnerability")
    if not isinstance(vulnerability, dict):
        raise ValueError(f"Sample {sample_id} missing expected_vulnerability.")
    _required_string(vulnerability, "canonical_id", sample_id=sample_id)
    matches = expected.get("expected_matches")
    if not isinstance(matches, list) or not matches:
        raise ValueError(f"Sample {sample_id} must define expected_matches.")
    for match in matches:
        _required_string(match, "agent_id", sample_id=sample_id)
        _required_string(match, "status", sample_id=sample_id)


def _required_string(
    data: dict[str, Any],
    field_name: str,
    *,
    sample_id: str | None = None,
) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        prefix = f"Sample {sample_id} " if sample_id else ""
        raise ValueError(f"{prefix}missing required string field {field_name}.")
    return value
