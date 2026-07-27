from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Asset, AssetFirewall, AssetFirewallRule, AssetSnapshot
from app.schemas.agent import AssetSnapshotIn


def _minimal_snapshot(**extra: object) -> dict[str, object]:
    return {
        "agent_id": "agent-firewall-001",
        "hostname": "firewall-host",
        **extra,
    }


def test_snapshot_distinguishes_legacy_omission_from_explicit_empty_collection() -> None:
    legacy = AssetSnapshotIn.model_validate(_minimal_snapshot())
    collected_empty = AssetSnapshotIn.model_validate(
        _minimal_snapshot(firewalls=[])
    )

    assert legacy.firewalls is None
    assert "firewalls" not in legacy.model_fields_set
    assert collected_empty.firewalls == []
    assert "firewalls" in collected_empty.model_fields_set


def test_snapshot_rejects_duplicate_or_unknown_firewall_engines() -> None:
    duplicate = {
        "firewalls": [
            {"engine": "nftables"},
            {"engine": "nftables"},
        ]
    }
    with pytest.raises(ValidationError, match="duplicate engines"):
        AssetSnapshotIn.model_validate(_minimal_snapshot(**duplicate))

    with pytest.raises(ValidationError):
        AssetSnapshotIn.model_validate(
            _minimal_snapshot(firewalls=[{"engine": "unknown-firewall"}])
        )


def test_asset_firewall_relationship_and_snapshot_counts(db_session: Session) -> None:
    asset = Asset(hostname="firewall-host", agent_id="agent-firewall-001")
    firewall = AssetFirewall(
        asset=asset,
        engine="nftables",
        role="backend",
        effective=True,
        runtime_state="active",
        collection_status="success",
    )
    firewall.rules = [
        AssetFirewallRule(
            scope="runtime",
            family="inet",
            table_name="filter",
            chain_name="input",
            rule_order=1,
            action="accept",
            protocol="tcp",
            destination_port="22",
            raw_rule="tcp dport 22 accept",
        )
    ]
    snapshot = AssetSnapshot(
        asset=asset,
        agent_id=asset.agent_id,
        hostname=asset.hostname,
        payload_hash="f" * 64,
        raw_payload={"firewalls": [{"engine": "nftables"}]},
        firewall_count=1,
        firewall_rule_count=1,
    )
    db_session.add_all([asset, firewall, snapshot])
    db_session.commit()
    db_session.refresh(asset)

    assert asset.firewalls == [firewall]
    assert firewall.rules[0].destination_port == "22"
    assert snapshot.firewall_count == 1
    assert snapshot.firewall_rule_count == 1


def test_asset_firewall_engine_is_unique_per_asset(db_session: Session) -> None:
    asset = Asset(hostname="duplicate-firewall-host")
    db_session.add(asset)
    db_session.flush()
    db_session.add_all(
        [
            AssetFirewall(
                asset_id=asset.id,
                engine="ufw",
                role="manager",
                runtime_state="active",
                collection_status="success",
            ),
            AssetFirewall(
                asset_id=asset.id,
                engine="ufw",
                role="manager",
                runtime_state="inactive",
                collection_status="success",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_firewall_database_status_constraints(db_session: Session) -> None:
    asset = Asset(hostname="invalid-firewall-host")
    db_session.add(asset)
    db_session.flush()
    db_session.add(
        AssetFirewall(
            asset_id=asset.id,
            engine="nftables",
            role="invalid-role",
            runtime_state="active",
            collection_status="success",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
