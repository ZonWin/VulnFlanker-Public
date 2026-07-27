from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Vulnerability, VulnerabilitySource
from app.schemas.intel import WatchVulnWebhookEnvelope
from app.services.intel_ingestion import store_raw_event
from app.services.intel_normalization import normalize_raw_event
from app.services.intel_tracking import _quality_for_vulnerability
from app.services.vulnerability_readiness import evaluate_vulnerability_readiness


CORPUS_ROOT = Path(__file__).parent / "fixtures" / "public_watchvuln_corpus"


def test_public_watchvuln_corpus_manifest_and_payloads_are_valid() -> None:
    manifest = _load_json(CORPUS_ROOT / "manifest.json")
    raw_lines = [
        line
        for line in (CORPUS_ROOT / "raw.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert manifest["schema_version"] == "watchvuln-public-corpus-v1"
    assert manifest["total_records"] == 3
    assert len(raw_lines) == manifest["total_records"]
    assert len(manifest["records"]) == manifest["total_records"]

    source_counts: Counter[str] = Counter()
    field_coverage: Counter[str] = Counter()
    for record, raw_line in zip(manifest["records"], raw_lines, strict=True):
        payload = json.loads(raw_line)
        envelope = WatchVulnWebhookEnvelope.model_validate(payload)
        content = envelope.content
        source = content.get("watchvuln_source") or "unknown"

        assert envelope.type == "watchvuln-vulninfo"
        assert source == record["source"]
        assert content.get("unique_key") == record["unique_key"]

        source_counts[source] += 1
        if content.get("cve"):
            field_coverage["has_cve"] += 1
        if content.get("description"):
            field_coverage["has_description"] += 1
        if content.get("solutions"):
            field_coverage["has_solution"] += 1
        if content.get("from"):
            field_coverage["has_source_url"] += 1
        references = content.get("references")
        if isinstance(references, list) and references:
            field_coverage["has_references"] += 1

        raw_event_path = CORPUS_ROOT / record["raw_event_file"]
        raw_event = _load_json(raw_event_path)
        assert raw_event["provider"] == "watchvuln"
        assert raw_event["event_type"] == "watchvuln-vulninfo"
        assert raw_event["external_key"] == record["unique_key"]
        WatchVulnWebhookEnvelope.model_validate(raw_event["payload"])

    assert dict(sorted(source_counts.items())) == manifest["source_counts"]
    assert {
        key: field_coverage[key]
        for key in sorted(manifest["field_coverage"])
    } == manifest["field_coverage"]


def test_public_watchvuln_corpus_normalizes_all_raw_events(db_session: Session) -> None:
    manifest = _load_json(CORPUS_ROOT / "manifest.json")
    status_counts: Counter[str] = Counter()
    external_canonical_count = 0

    for record in manifest["records"]:
        raw_event_data = _load_json(CORPUS_ROOT / record["raw_event_file"])
        raw_event, created = store_raw_event(
            db_session,
            provider=raw_event_data["provider"],
            event_type=raw_event_data["event_type"],
            external_key=raw_event_data["external_key"],
            payload=raw_event_data["payload"],
            source_url=raw_event_data.get("source_url"),
        )

        assert created is True
        result = normalize_raw_event(db_session, raw_event)

        status_counts[result.status] += 1
        assert result.status == "processed"
        assert result.vulnerability_id
        assert result.canonical_id
        if not record["has_cve"]:
            assert result.canonical_id == record["unique_key"]
            external_canonical_count += 1

    vulnerabilities = db_session.scalars(
        select(Vulnerability).options(
            selectinload(Vulnerability.sources).selectinload(VulnerabilitySource.raw_event)
        )
    ).all()
    source_count = db_session.scalar(select(func.count(VulnerabilitySource.id)))
    issue_distribution: Counter[str] = Counter()
    readiness_distribution: Counter[str] = Counter()
    readiness_reason_distribution: Counter[str] = Counter()
    source_conflict_count = 0
    for vulnerability in vulnerabilities:
        quality = _quality_for_vulnerability(vulnerability)
        assert quality is not None
        source_conflict_count += quality.source_conflict_count
        issue_distribution.update(quality.issue_codes)
        readiness = evaluate_vulnerability_readiness(vulnerability)
        readiness_distribution[readiness.match_readiness] += 1
        readiness_reason_distribution.update(readiness.reasons)

    assert status_counts == {"processed": manifest["total_records"]}
    assert source_count == manifest["total_records"]
    assert len(vulnerabilities) == 3
    assert external_canonical_count == 1
    assert source_conflict_count == 0
    assert issue_distribution == {
        "missing_affected_versions": 2,
        "missing_exploitation_signal": 2,
        "missing_fixed_versions": 2,
        "missing_product": 1,
        "missing_references": 1,
    }
    assert readiness_distribution == {
        "needs_enrichment": 1,
        "not_matchable": 1,
        "ready": 1,
    }
    assert readiness_reason_distribution["missing_product"] == 1
    assert readiness_reason_distribution["missing_affected_versions"] == 2
    assert readiness_reason_distribution["missing_fixed_versions"] == 2
    assert readiness_reason_distribution["no_asset_match_terms"] == 1


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    assert isinstance(data, dict)
    return data
