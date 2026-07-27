from __future__ import annotations

from app.db.models import (
    AIEnrichmentBatchRun,
    Vulnerability,
    VulnerabilityAIEnrichment,
    VulnerabilitySource,
)


def _create_batch_fixture(db_session) -> tuple[str, str]:
    vulnerability = Vulnerability(
        canonical_id="CVE-2026-AI-BATCH",
        title="AI batch detail fixture",
        vendor=None,
        product=None,
        affected_versions=None,
        fixed_versions=None,
    )
    db_session.add(vulnerability)
    db_session.flush()

    source = VulnerabilitySource(
        vulnerability_id=vulnerability.id,
        source_name="watchvuln",
        event_type="vulnerability",
        external_id="WV-2026-001",
        source_url="https://example.test/advisory",
        title="Source advisory",
        description="Upstream source text",
        references_json=["https://example.test/ref"],
        tags_json=["rce"],
        last_payload_hash="source-hash",
    )
    enrichment = VulnerabilityAIEnrichment(
        id="enrichment-batch-detail-1",
        vulnerability_id=vulnerability.id,
        layer="existing_data_extraction",
        source_mode="existing_raw",
        profile_id=None,
        model="fake-json-model",
        input_hash="batch-detail-input",
        status="pending_review",
        vendor="Example",
        product="Example Product",
        affected_versions="< 1.2.3",
        fixed_versions="1.2.3",
        remediation="Upgrade to 1.2.3.",
        confidence=0.91,
        evidence_json=[
            {
                "field": "product",
                "source_type": "source",
                "source_url": "https://example.test/advisory",
                "quote": "Example Product before 1.2.3 is affected.",
                "confidence": 0.91,
            }
        ],
        source_urls_json=["https://example.test/advisory"],
        conflicts_json=[],
        raw_output_json={"product": "Example Product"},
    )
    batch = AIEnrichmentBatchRun(
        status="completed",
        trigger_type="manual",
        filters_json={
            "selected_ids": [vulnerability.id],
            "result_enrichment_ids": {
                vulnerability.id: enrichment.id,
            },
            "layer": "existing_data_extraction",
            "limit": 100,
        },
        allow_web_enrichment=False,
        selected_count=1,
        processed_count=1,
        success_count=1,
        pending_review_count=1,
    )
    db_session.add_all([source, enrichment, batch])
    db_session.commit()
    return batch.id, vulnerability.id


def test_ai_enrichment_batch_detail_exposes_sources_and_result(client, db_session) -> None:
    batch_id, _ = _create_batch_fixture(db_session)

    response = client.get(f"/api/v1/vulnerability-ai-enrichments/batch/{batch_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch"]["id"] == batch_id
    assert payload["batch"]["processed_count"] == 1
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["vulnerability"]["canonical_id"] == "CVE-2026-AI-BATCH"
    assert item["vulnerability"]["sources"][0]["source_name"] == "watchvuln"
    assert item["enrichment"]["product"] == "Example Product"
    assert item["enrichment"]["evidence"][0]["quote"]
    assert item["enrichment"]["quality_gate"] is not None


def test_task_center_ai_enrichment_item_links_to_batch_detail(client, db_session) -> None:
    batch_id, _ = _create_batch_fixture(db_session)

    response = client.get(
        "/api/v1/task-center/items",
        params={"item_type": "ai_enrichment"},
    )

    assert response.status_code == 200
    item = next(row for row in response.json() if row["raw_id"] == batch_id)
    assert item["detail_path"] == f"/ai-enrichments/batches/{batch_id}"
