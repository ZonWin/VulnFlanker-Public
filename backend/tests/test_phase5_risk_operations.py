from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.base import utcnow
from app.db.models import MatchResult, Vulnerability, VulnerabilitySource
from test_asset_ingestion import build_linux_snapshot


def _snapshot(
    *,
    agent_id: str,
    hostname: str,
    exposure_type: str,
    is_public: bool,
    criticality: str,
) -> dict[str, object]:
    snapshot = build_linux_snapshot(nginx_version="1.24.0")
    snapshot["agent_id"] = agent_id
    snapshot["hostname"] = hostname
    snapshot["collected_at"] = utcnow().isoformat()
    snapshot["exposure_type"] = exposure_type
    snapshot["criticality"] = criticality
    exposures = snapshot["exposures"]
    assert isinstance(exposures, list)
    exposure = exposures[0]
    assert isinstance(exposure, dict)
    exposure["is_public"] = is_public
    exposure["address"] = "203.0.113.20" if is_public else "10.10.20.15"
    return snapshot


def _create_vulnerability(
    db_session: Session,
    *,
    canonical_id: str,
    severity_cvss: float,
    kev_status: bool = False,
) -> Vulnerability:
    vulnerability = Vulnerability(
        canonical_id=canonical_id,
        title=f"{canonical_id} nginx vulnerability",
        vendor="nginx",
        product="nginx",
        severity_label="high",
        severity_cvss=severity_cvss,
        kev_status=kev_status,
        poc_status=True,
        affected_versions="< 1.25.0",
        fixed_versions="1.25.0",
    )
    db_session.add(vulnerability)
    db_session.flush()
    db_session.add(
        VulnerabilitySource(
            vulnerability_id=vulnerability.id,
            source_name="test-source",
            external_id=canonical_id,
            source_url=f"https://example.test/vulns/{canonical_id}",
            title=vulnerability.title,
            description="Test source record for a match-ready vulnerability.",
            severity_raw="high",
            references_json=[f"https://example.test/references/{canonical_id}"],
            last_payload_hash=f"hash-{canonical_id}",
        )
    )
    db_session.commit()
    return vulnerability


def test_risk_queue_explains_and_sorts_operational_priority(client, db_session) -> None:
    internal_asset = client.post(
        "/api/v1/agents/snapshots",
        json=_snapshot(
            agent_id="agent-internal-001",
            hostname="web-internal.prod.local",
            exposure_type="internal",
            is_public=False,
            criticality="medium",
        ),
    ).json()
    public_asset = client.post(
        "/api/v1/agents/snapshots",
        json=_snapshot(
            agent_id="agent-public-001",
            hostname="web-public.prod.local",
            exposure_type="internet",
            is_public=True,
            criticality="high",
        ),
    ).json()
    high_internal_vuln = _create_vulnerability(
        db_session,
        canonical_id="CVE-2026-5501",
        severity_cvss=9.8,
        kev_status=False,
    )
    medium_public_kev_vuln = _create_vulnerability(
        db_session,
        canonical_id="CVE-2026-5502",
        severity_cvss=6.0,
        kev_status=True,
    )

    client.post(
        "/api/v1/match-results/evaluate",
        json={
            "asset_id": internal_asset["asset_id"],
            "vulnerability_id": high_internal_vuln.canonical_id,
        },
    )

    client.post(
        "/api/v1/match-results/evaluate",
        json={
            "asset_id": public_asset["asset_id"],
            "vulnerability_id": medium_public_kev_vuln.canonical_id,
        },
    )

    stored_result = db_session.scalar(
        select(MatchResult).where(MatchResult.vulnerability_id == medium_public_kev_vuln.id)
    )
    assert stored_result is not None
    assert stored_result.risk_model_version == "risk-v2.0"
    assert stored_result.risk_priority == "high"
    assert stored_result.risk_factors_json
    assert stored_result.risk_explanation

    response = client.get("/api/v1/match-results/risk-queue")

    assert response.status_code == 200
    payload = response.json()
    assert [item["vulnerability_canonical_id"] for item in payload] == [
        "CVE-2026-5502",
        "CVE-2026-5501",
    ]
    assert payload[0]["risk_score"] > payload[1]["risk_score"]
    assert payload[0]["risk_priority"] == "high"
    assert payload[0]["risk_explanation"]
    assert {
        "severity",
        "exploitability",
        "exposure",
        "business_criticality",
        "confidence",
        "verification",
        "asset_freshness",
    }.issubset({factor["name"] for factor in payload[0]["risk_factors"]})
    assert payload[0]["risk_model_version"] == "risk-v2.0"
    assert "risk-v2.0" in payload[0]["risk_explanation"]

    filtered_response = client.get(
        "/api/v1/match-results/risk-queue"
        "?risk_priority=high&asset_criticality=high&exposure_type=internet"
    )

    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert [item["vulnerability_canonical_id"] for item in filtered_payload] == [
        "CVE-2026-5502"
    ]


def test_risk_config_endpoint_exposes_active_weights(client) -> None:
    response = client.get("/api/v1/match-results/risk-config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_version"] == "risk-v2.0"
    assert payload["weights"] == {
        "severity": 0.3,
        "exploitability": 0.18,
        "exposure": 0.15,
        "business_criticality": 0.17,
        "confidence": 0.08,
        "verification": 0.07,
        "asset_freshness": 0.05,
    }
    assert payload["weight_total"] == 1.0
    assert payload["warnings"] == []
    assert payload["priority_thresholds"]["high"] == 7.0


def test_risk_rankings_group_by_vulnerability_and_asset(client, db_session) -> None:
    asset = client.post(
        "/api/v1/agents/snapshots",
        json=_snapshot(
            agent_id="agent-public-002",
            hostname="web-public-2.prod.local",
            exposure_type="internet",
            is_public=True,
            criticality="critical",
        ),
    ).json()
    vulnerability = _create_vulnerability(
        db_session,
        canonical_id="CVE-2026-5503",
        severity_cvss=7.5,
        kev_status=True,
    )
    client.post(
        "/api/v1/match-results/evaluate",
        json={
            "asset_id": asset["asset_id"],
            "vulnerability_id": vulnerability.canonical_id,
        },
    )

    vulnerability_response = client.get("/api/v1/match-results/rankings/vulnerabilities")
    asset_response = client.get("/api/v1/match-results/rankings/assets")

    assert vulnerability_response.status_code == 200
    vulnerability_payload = vulnerability_response.json()
    assert vulnerability_payload[0]["vulnerability_canonical_id"] == "CVE-2026-5503"
    assert vulnerability_payload[0]["affected_count"] == 1
    assert vulnerability_payload[0]["top_asset_hostname"] == "web-public-2.prod.local"

    assert asset_response.status_code == 200
    asset_payload = asset_response.json()
    assert asset_payload[0]["asset_hostname"] == "web-public-2.prod.local"
    assert asset_payload[0]["asset_criticality"] == "critical"
    assert asset_payload[0]["top_vulnerability_canonical_id"] == "CVE-2026-5503"
