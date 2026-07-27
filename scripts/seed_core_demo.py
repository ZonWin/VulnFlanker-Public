from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select

from app.db.models import Asset, MatchResult, VerificationTask, Vulnerability
from app.db.session import SessionLocal
from app.schemas.agent import AssetSnapshotIn
from app.schemas.verification import VerificationTaskCreateIn
from app.services.agent_ingestion import ingest_asset_snapshot
from app.services.matching import evaluate_matches
from app.services.verification_orchestrator import (
    apply_verification_result_to_match_result,
    run_local_verification_task,
)
from app.services.verification_tasks import create_verification_task


C0_VULNERABILITIES = [
    {
        "canonical_id": "CVE-2026-C0-0001",
        "title": "C0 Nginx Fixed Version Demo Vulnerability",
        "vendor": "Nginx",
        "product": "nginx",
        "description": "C0 demo vulnerability with a known fixed version.",
        "severity_label": "critical",
        "severity_cvss": 9.8,
        "kev_status": True,
        "known_ransomware_campaign_use": "Known",
        "wild_exploitation_status": True,
        "fixed_versions": "1.25.0",
        "remediation": "Upgrade nginx to version 1.25.0 or later.",
        "notes": json.dumps(
            {
                "requires_public_access": True,
                "affected_os": ["linux", "ubuntu"],
            }
        ),
    },
    {
        "canonical_id": "CVE-2026-C0-0002",
        "title": "C0 Nginx Review Required Demo Vulnerability",
        "vendor": "Nginx",
        "product": "nginx",
        "description": "C0 demo vulnerability without structured version data.",
        "severity_label": "high",
        "severity_cvss": 8.1,
        "kev_status": True,
        "known_ransomware_campaign_use": "Unknown",
        "wild_exploitation_status": True,
        "fixed_versions": None,
        "remediation": "Review the vendor advisory and apply the recommended update.",
        "notes": json.dumps(
            {
                "requires_public_access": True,
                "affected_os": ["linux", "ubuntu"],
            }
        ),
    },
]


def _base_snapshot(*, agent_id: str, hostname: str, nginx_version: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "agent_id": agent_id,
        "agent_version": "0.1.0",
        "hostname": hostname,
        "primary_ip": "10.10.20.15",
        "platform": "linux",
        "os_family": "ubuntu",
        "os_version": "22.04",
        "kernel_version": "5.15.0-105-generic",
        "architecture": "x86_64",
        "environment_type": "production",
        "exposure_type": "internet",
        "business_system": "c0-demo",
        "owner_team": "security",
        "owner_person": "demo-operator",
        "criticality": "high",
        "allow_auto_verify": True,
        "allow_auto_remediate": False,
        "components": [
            {
                "component_name": "nginx",
                "component_type": "package",
                "version": nginx_version,
                "source_type": "dpkg",
                "install_path": "/usr/sbin/nginx",
            },
            {
                "component_name": "openssl",
                "component_type": "package",
                "version": "3.0.2",
                "source_type": "dpkg",
            },
        ],
        "exposures": [
            {
                "exposure_kind": "network_service",
                "address": "203.0.113.20",
                "port": 443,
                "protocol": "tcp",
                "service_name": "https",
                "product": "nginx",
                "version": nginx_version,
                "state": "open",
                "is_public": True,
                "banner": "nginx",
            }
        ],
        "collected_at": "2026-05-10T00:00:00Z",
    }
    return payload


C0_ASSETS = [
    _base_snapshot(
        agent_id="c0-agent-affected",
        hostname="c0-web-affected.local",
        nginx_version="1.24.0",
    ),
    _base_snapshot(
        agent_id="c0-agent-safe",
        hostname="c0-web-safe.local",
        nginx_version="1.26.0",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed deterministic C0 core-chain demo data.",
    )
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Seed vulnerabilities, assets, and matches without creating verification evidence.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as db:
        vulnerabilities = [_upsert_vulnerability(db, item) for item in C0_VULNERABILITIES]
        db.commit()

        asset_ids = []
        for payload in C0_ASSETS:
            result = ingest_asset_snapshot(db, AssetSnapshotIn.model_validate(payload))
            asset_ids.append(result.asset_id)

        match_results = evaluate_matches(db)
        verified_task_id = None
        if not args.skip_verification:
            verified_task_id = _ensure_verification_evidence(db)

        summary = _build_summary(
            db,
            vulnerability_ids=[item.id for item in vulnerabilities],
            asset_ids=asset_ids,
            verified_task_id=verified_task_id,
        )

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


def _upsert_vulnerability(db, data: dict[str, Any]) -> Vulnerability:
    vulnerability = db.scalar(
        select(Vulnerability).where(Vulnerability.canonical_id == data["canonical_id"])
    )
    if vulnerability is None:
        vulnerability = Vulnerability(**data)
        db.add(vulnerability)
        db.flush()
        return vulnerability

    for field_name, value in data.items():
        setattr(vulnerability, field_name, copy.deepcopy(value))
    db.add(vulnerability)
    db.flush()
    return vulnerability


def _ensure_verification_evidence(db) -> str | None:
    affected_result = db.scalar(
        select(MatchResult)
        .join(MatchResult.vulnerability)
        .join(MatchResult.asset)
        .where(
            Vulnerability.canonical_id == "CVE-2026-C0-0001",
            Asset.agent_id == "c0-agent-affected",
        )
    )
    if affected_result is None:
        return None

    existing_task = db.scalar(
        select(VerificationTask)
        .where(
            VerificationTask.match_result_id == affected_result.id,
            VerificationTask.task_type == "package_version_check",
            VerificationTask.status == "completed",
        )
        .order_by(VerificationTask.created_at.desc())
    )
    if existing_task is not None:
        apply_verification_result_to_match_result(
            db,
            existing_task,
            actor_type="script",
            actor_id="seed_core_demo",
        )
        db.commit()
        return existing_task.id

    task = create_verification_task(
        db,
        VerificationTaskCreateIn(
            match_result_id=affected_result.id,
            task_type="package_version_check",
            requested_by="seed_core_demo",
        ),
    )
    if task is None:
        return None
    run_local_verification_task(db, task.id)
    return task.id


def _build_summary(
    db,
    *,
    vulnerability_ids: list[str],
    asset_ids: list[str],
    verified_task_id: str | None,
) -> dict[str, Any]:
    results = db.scalars(
        select(MatchResult)
        .join(MatchResult.vulnerability)
        .join(MatchResult.asset)
        .where(
            MatchResult.vulnerability_id.in_(vulnerability_ids),
            MatchResult.asset_id.in_(asset_ids),
        )
        .order_by(MatchResult.risk_score.desc(), MatchResult.updated_at.desc())
    ).all()
    return {
        "status": "seeded",
        "vulnerabilities": [
            vulnerability.canonical_id
            for vulnerability in db.scalars(
                select(Vulnerability).where(Vulnerability.id.in_(vulnerability_ids))
            ).all()
        ],
        "assets": [
            asset.agent_id
            for asset in db.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()
        ],
        "match_results": [
            {
                "id": result.id,
                "vulnerability": result.vulnerability.canonical_id,
                "asset": result.asset.agent_id,
                "status": result.status,
                "risk_score": result.risk_score,
            }
            for result in results
        ],
        "verified_task_id": verified_task_id,
    }


if __name__ == "__main__":
    raise SystemExit(main())

