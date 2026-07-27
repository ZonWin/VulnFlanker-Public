from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.db.models import Asset, BusinessSystem, Person, User
from app.schemas.asset import AssetBusinessSystemBulkBindingOut, AssetDetail
from app.services.asset_catalog import get_asset
from app.services.audit import create_audit_log
from app.services.ownership import OwnershipServiceError


def bind_asset_business_system(
    db: Session,
    asset_id: str,
    business_system_id: str | None,
    *,
    actor: User,
) -> AssetDetail:
    asset = _get_asset_model(db, asset_id)
    system = _get_active_system(db, business_system_id)
    previous_system = asset.business_system_record
    if (
        asset.business_system_id == business_system_id
        and asset.ownership_source == "manual"
    ):
        detail = get_asset(db, asset.id)
        assert detail is not None
        return detail

    _apply_binding(asset, system, source="manual")
    action = (
        "ownership.asset.unassigned"
        if system is None
        else "ownership.asset.assigned"
    )
    create_audit_log(
        db,
        action=action,
        resource_type="asset",
        resource_id=asset.id,
        actor_type="user",
        actor_id=actor.id,
        summary=(
            f"Unassigned asset {asset.hostname} from its business system."
            if system is None
            else f"Assigned asset {asset.hostname} to {system.code}."
        ),
        details={
            "asset_id": asset.id,
            "before_business_system_id": (
                previous_system.id if previous_system is not None else None
            ),
            "before_business_system_name": (
                previous_system.name if previous_system is not None else None
            ),
            "after_business_system_id": system.id if system is not None else None,
            "after_business_system_name": system.name if system is not None else None,
            "source": "manual",
        },
    )
    db.commit()
    detail = get_asset(db, asset.id)
    assert detail is not None
    return detail


def bulk_bind_asset_business_systems(
    db: Session,
    asset_ids: list[str],
    business_system_id: str | None,
    *,
    actor: User,
) -> AssetBusinessSystemBulkBindingOut:
    system = _get_active_system(db, business_system_id)
    assets = _get_asset_models(db, asset_ids)
    previous_bindings = {
        asset.id: asset.business_system_id for asset in assets
    }
    changed_assets = [
        asset
        for asset in assets
        if asset.business_system_id != business_system_id
        or asset.ownership_source != "manual"
    ]
    for asset in changed_assets:
        _apply_binding(asset, system, source="manual")

    create_audit_log(
        db,
        action="ownership.asset.bulk_assigned",
        resource_type="asset_binding_batch",
        actor_type="user",
        actor_id=actor.id,
        summary=(
            f"Unassigned {len(changed_assets)} assets from business systems."
            if system is None
            else f"Assigned {len(changed_assets)} assets to {system.code}."
        ),
        details={
            "asset_ids": [asset.id for asset in assets],
            "changed_asset_ids": [asset.id for asset in changed_assets],
            "before_business_system_ids": previous_bindings,
            "after_business_system_id": system.id if system is not None else None,
            "after_business_system_name": system.name if system is not None else None,
            "source": "manual",
        },
    )
    db.commit()
    return AssetBusinessSystemBulkBindingOut(
        updated_count=len(changed_assets),
        asset_ids=[asset.id for asset in assets],
        business_system_id=system.id if system is not None else None,
    )


def _get_asset_model(db: Session, asset_id: str) -> Asset:
    asset = db.scalar(
        select(Asset)
        .options(selectinload(Asset.business_system_record))
        .where(or_(Asset.id == asset_id, Asset.agent_id == asset_id))
    )
    if asset is None:
        raise OwnershipServiceError(
            "resource_not_found",
            "Asset was not found.",
            status_code=404,
            details={"resource_type": "asset", "resource_id": asset_id},
        )
    return asset


def _get_asset_models(db: Session, asset_ids: list[str]) -> list[Asset]:
    assets = list(
        db.scalars(
            select(Asset)
            .options(selectinload(Asset.business_system_record))
            .where(or_(Asset.id.in_(asset_ids), Asset.agent_id.in_(asset_ids)))
        ).all()
    )
    by_identifier: dict[str, Asset] = {}
    for asset in assets:
        by_identifier[asset.id] = asset
        if asset.agent_id:
            by_identifier[asset.agent_id] = asset
    missing = [asset_id for asset_id in asset_ids if asset_id not in by_identifier]
    if missing:
        raise OwnershipServiceError(
            "resource_not_found",
            "One or more assets were not found.",
            status_code=404,
            details={"resource_type": "asset", "missing_asset_ids": missing},
        )
    return [by_identifier[asset_id] for asset_id in asset_ids]


def _get_active_system(
    db: Session,
    business_system_id: str | None,
) -> BusinessSystem | None:
    if business_system_id is None:
        return None
    system = db.scalar(
        select(BusinessSystem)
        .options(
            selectinload(BusinessSystem.responsible_person).selectinload(Person.team)
        )
        .where(BusinessSystem.id == business_system_id)
    )
    if system is None:
        raise OwnershipServiceError(
            "resource_not_found",
            "Business system was not found.",
            status_code=404,
            details={
                "resource_type": "business_system",
                "resource_id": business_system_id,
            },
        )
    person = system.responsible_person
    if (
        system.status != "active"
        or person is None
        or person.status != "active"
        or person.team.status != "active"
    ):
        raise OwnershipServiceError(
            "invalid_relationship",
            "Assets can only be assigned to an active business system with an active responsibility chain.",
            details={"business_system_id": system.id, "status": system.status},
        )
    return system


def _apply_binding(
    asset: Asset,
    system: BusinessSystem | None,
    *,
    source: str,
) -> None:
    asset.business_system_record = system
    asset.ownership_source = source
    asset.ownership_updated_at = utcnow()
