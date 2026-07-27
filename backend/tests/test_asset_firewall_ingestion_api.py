from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Asset, AssetFirewall, AssetSnapshot


def build_firewall_snapshot(*, collected_at: str = "2026-07-20T08:00:00Z") -> dict:
    return {
        "agent_id": "agent-firewall-001",
        "agent_version": "0.2.0",
        "hostname": "firewall-host.prod.local",
        "primary_ip": "10.20.30.40",
        "platform": "linux",
        "os_family": "ubuntu",
        "os_version": "24.04",
        "architecture": "x86_64",
        "environment_type": "production",
        "exposure_type": "internal",
        "criticality": "high",
        "components": [],
        "exposures": [],
        "collected_at": collected_at,
        "firewalls": [
            {
                "engine": "firewalld",
                "role": "manager",
                "backend": "nftables",
                "effective": True,
                "installed": True,
                "runtime_state": "active",
                "service_enabled": True,
                "collection_status": "success",
                "raw_runtime": "public (active)\n  ports: 8443/tcp",
                "raw_permanent": "public\n  services: ssh",
                "rules": [
                    {
                        "scope": "runtime",
                        "family": "ipv4",
                        "zone": "public",
                        "order": 0,
                        "rule_kind": "port",
                        "action": "accept",
                        "protocol": "tcp",
                        "destination_port": "8443",
                        "in_interface": "eth0",
                        "state_match": "NEW",
                        "raw_rule": "8443/tcp",
                    },
                    {
                        "scope": "runtime",
                        "family": "ipv4",
                        "zone": "public",
                        "order": 1,
                        "rule_kind": "rich_rule",
                        "action": "drop",
                        "source": "198.51.100.0/24",
                        "raw_rule": "rule source address=198.51.100.0/24 drop",
                    },
                    {
                        "scope": "permanent",
                        "family": "inet",
                        "zone": "public",
                        "order": 2,
                        "rule_kind": "service",
                        "action": "accept",
                        "destination_port": "ssh",
                        "raw_rule": "ssh",
                    },
                ],
            },
            {
                "engine": "iptables",
                "role": "compatibility",
                "backend": "nftables",
                "managed_by": "firewalld",
                "effective": False,
                "installed": True,
                "runtime_state": "active",
                "collection_status": "success",
                "raw_runtime": "*filter\n-A INPUT -j ACCEPT\nCOMMIT",
                "rules": [
                    {
                        "scope": "runtime",
                        "family": "ipv4",
                        "table": "filter",
                        "chain": "INPUT",
                        "order": 0,
                        "rule_kind": "rule",
                        "action": "accept",
                        "raw_rule": "-A INPUT -j ACCEPT",
                    }
                ],
            },
        ],
    }


def test_firewall_ingestion_and_read_apis(client, db_session) -> None:
    response = client.post(
        "/api/v1/agents/snapshots",
        json=build_firewall_snapshot(),
    )
    assert response.status_code == 202
    assert response.json()["firewall_count"] == 2
    assert response.json()["firewall_rule_count"] == 4
    asset_id = response.json()["asset_id"]

    snapshot = db_session.scalar(select(AssetSnapshot))
    assert snapshot is not None
    assert snapshot.firewall_count == 2
    assert snapshot.firewall_rule_count == 4

    detail_response = client.get(f"/api/v1/assets/{asset_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["latest_snapshot"]["firewall_count"] == 2
    assert detail_response.json()["latest_snapshot"]["firewall_rule_count"] == 4

    summary_response = client.get(f"/api/v1/assets/{asset_id}/firewalls")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["total"] == 2
    assert [item["engine"] for item in summary["items"]] == [
        "firewalld",
        "iptables",
    ]
    assert summary["items"][0]["runtime_rule_count"] == 2
    assert summary["items"][0]["permanent_rule_count"] == 1
    assert summary["items"][1]["role"] == "compatibility"
    assert summary["items"][1]["effective"] is False

    rules_response = client.get(
        f"/api/v1/assets/{asset_id}/firewalls/firewalld/rules",
        params={"scope": "runtime", "action": "accept", "page_size": 1},
    )
    assert rules_response.status_code == 200
    rules = rules_response.json()
    assert rules["total"] == 1
    assert rules["page"] == 1
    assert rules["page_size"] == 1
    assert rules["items"][0]["destination_port"] == "8443"
    assert rules["items"][0]["in_interface"] == "eth0"
    assert rules["items"][0]["state_match"] == "NEW"

    search_response = client.get(
        f"/api/v1/assets/{asset_id}/firewalls/firewalld/rules",
        params={"search": "198.51.100"},
    )
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 1
    assert search_response.json()["items"][0]["action"] == "drop"

    raw_response = client.get(
        f"/api/v1/assets/{asset_id}/firewalls/firewalld/raw",
        params={"scope": "permanent"},
    )
    assert raw_response.status_code == 200
    assert raw_response.json()["scope"] == "permanent"
    assert "services: ssh" in raw_response.json()["content"]


def test_firewall_success_replaces_failure_preserves_and_empty_clears(
    client,
    db_session,
) -> None:
    first = client.post(
        "/api/v1/agents/snapshots",
        json=build_firewall_snapshot(),
    )
    assert first.status_code == 202

    replacement = build_firewall_snapshot(collected_at="2026-07-20T08:05:00Z")
    replacement["firewalls"] = [deepcopy(replacement["firewalls"][0])]
    replacement_firewall = replacement["firewalls"][0]
    replacement_firewall["raw_runtime"] = "public (active)\n  ports: 9443/tcp"
    replacement_firewall["rules"] = [
        {
            "scope": "runtime",
            "family": "ipv4",
            "zone": "public",
            "order": 0,
            "rule_kind": "port",
            "action": "accept",
            "protocol": "tcp",
            "destination_port": "9443",
            "raw_rule": "9443/tcp",
        }
    ]
    assert client.post("/api/v1/agents/snapshots", json=replacement).status_code == 202

    db_session.expire_all()
    asset = db_session.scalar(
        select(Asset)
        .options(selectinload(Asset.firewalls).selectinload(AssetFirewall.rules))
        .where(Asset.agent_id == "agent-firewall-001")
    )
    assert asset is not None
    assert len(asset.firewalls) == 1
    firewall = asset.firewalls[0]
    assert firewall.raw_runtime.endswith("9443/tcp")
    assert [rule.destination_port for rule in firewall.rules] == ["9443"]
    successful_at = firewall.last_success_at

    failed = build_firewall_snapshot(collected_at="2026-07-20T08:10:00Z")
    failed["firewalls"] = [
        {
            "engine": "firewalld",
            "role": "manager",
            "backend": "nftables",
            "effective": False,
            "installed": True,
            "runtime_state": "unknown",
            "collection_status": "permission_denied",
            "error_code": "permission_denied",
            "error_message": "You need to be root",
            "rules": [],
        }
    ]
    assert client.post("/api/v1/agents/snapshots", json=failed).status_code == 202

    db_session.expire_all()
    firewall = db_session.scalar(
        select(AssetFirewall).options(selectinload(AssetFirewall.rules))
    )
    assert firewall is not None
    assert firewall.collection_status == "permission_denied"
    assert firewall.error_code == "permission_denied"
    assert firewall.raw_runtime.endswith("9443/tcp")
    assert [rule.destination_port for rule in firewall.rules] == ["9443"]
    assert firewall.last_success_at == successful_at
    assert firewall.last_attempt_at > successful_at

    legacy = build_firewall_snapshot(collected_at="2026-07-20T08:15:00Z")
    legacy.pop("firewalls")
    assert client.post("/api/v1/agents/snapshots", json=legacy).status_code == 202
    db_session.expire_all()
    assert db_session.scalar(select(AssetFirewall)) is not None

    clear = build_firewall_snapshot(collected_at="2026-07-20T08:20:00Z")
    clear["firewalls"] = []
    clear_response = client.post("/api/v1/agents/snapshots", json=clear)
    assert clear_response.status_code == 202
    assert clear_response.json()["firewall_count"] == 0
    db_session.expire_all()
    assert db_session.scalar(select(AssetFirewall)) is None


def test_firewall_read_apis_require_login(anonymous_client) -> None:
    response = anonymous_client.get(
        "/api/v1/assets/asset-id/firewalls"
    )
    assert response.status_code == 401
