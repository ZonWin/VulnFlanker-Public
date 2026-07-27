from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_superuser
from app.db.models import User
from app.schemas.asset import (
    AssetBusinessSystemBinding,
    AssetBusinessSystemBulkBinding,
    AssetBusinessSystemBulkBindingOut,
    AssetDeleteRequest,
    AssetDetail,
    AssetFirewallList,
    AssetFirewallRawOut,
    AssetFirewallRuleList,
    AssetListPage,
    AssetMetadataUpdate,
    AssetSummary,
)
from app.schemas.agent import LifecycleActionOut
from app.services.asset_lifecycle import delete_asset as delete_asset_lifecycle
from app.services.asset_catalog import (
    get_asset,
    get_asset_firewall_raw,
    list_asset_firewall_rules,
    list_asset_firewalls,
    list_assets,
    list_assets_page,
    update_asset_metadata,
)
from app.services.asset_ownership import (
    bind_asset_business_system,
    bulk_bind_asset_business_systems,
)
from app.services.ownership import OwnershipServiceError

router = APIRouter()


@router.get("", response_model=AssetListPage | list[AssetSummary])
async def get_assets(
    business_system_id: str | None = Query(default=None, max_length=36),
    responsible_person_id: str | None = Query(default=None, max_length=36),
    responsibility_team_id: str | None = Query(default=None, max_length=36),
    ownership_status: Literal[
        "complete", "unassigned", "system_incomplete"
    ]
    | None = Query(default=None),
    search: str | None = Query(default=None, max_length=256),
    criticality: str | None = Query(default=None, max_length=32),
    environment_type: str | None = Query(default=None, max_length=32),
    exposure_type: str | None = Query(default=None, max_length=32),
    platform: str | None = Query(default=None, max_length=64),
    os_family: str | None = Query(default=None, max_length=64),
    paged: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=300),
    db: Session = Depends(get_db),
) -> AssetListPage | list[AssetSummary]:
    if not paged:
        return list_assets(
            db,
            business_system_id=business_system_id,
            responsible_person_id=responsible_person_id,
            responsibility_team_id=responsibility_team_id,
            ownership_status=ownership_status,
            search=search,
            criticality=criticality,
            environment_type=environment_type,
            exposure_type=exposure_type,
            platform=platform,
            os_family=os_family,
        )
    return list_assets_page(
        db,
        business_system_id=business_system_id,
        responsible_person_id=responsible_person_id,
        responsibility_team_id=responsibility_team_id,
        ownership_status=ownership_status,
        search=search,
        criticality=criticality,
        environment_type=environment_type,
        exposure_type=exposure_type,
        platform=platform,
        os_family=os_family,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/business-system-bindings",
    response_model=AssetBusinessSystemBulkBindingOut,
)
async def post_asset_business_system_bindings(
    payload: AssetBusinessSystemBulkBinding,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AssetBusinessSystemBulkBindingOut:
    return _run(
        bulk_bind_asset_business_systems,
        db,
        payload.asset_ids,
        payload.business_system_id,
        actor=actor,
    )


@router.get("/{asset_id}", response_model=AssetDetail)
async def get_asset_detail(
    asset_id: str,
    db: Session = Depends(get_db),
) -> AssetDetail:
    asset = get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.delete("/{asset_id}", response_model=LifecycleActionOut)
async def delete_asset_route(
    asset_id: str,
    payload: AssetDeleteRequest | None = None,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> LifecycleActionOut:
    result = delete_asset_lifecycle(
        db,
        asset_id,
        delete_agent=bool(payload and payload.delete_agent),
        actor_id=current_user.id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return LifecycleActionOut(**result.__dict__)


@router.get("/{asset_id}/firewalls", response_model=AssetFirewallList)
async def get_asset_firewalls(
    asset_id: str,
    db: Session = Depends(get_db),
) -> AssetFirewallList:
    result = list_asset_firewalls(db, asset_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return result


@router.get(
    "/{asset_id}/firewalls/{engine}/rules",
    response_model=AssetFirewallRuleList,
)
async def get_asset_firewall_rules(
    asset_id: str,
    engine: Literal["firewalld", "ufw", "iptables", "nftables"],
    scope: Literal["runtime", "permanent"] | None = Query(default=None),
    family: str | None = Query(default=None, max_length=16),
    action: str | None = Query(default=None, max_length=64),
    protocol: str | None = Query(default=None, max_length=32),
    search: str | None = Query(default=None, max_length=256),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AssetFirewallRuleList:
    result = list_asset_firewall_rules(
        db,
        asset_id,
        engine,
        scope=scope,
        family=family,
        action=action,
        protocol=protocol,
        search=search,
        page=page,
        page_size=page_size,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Asset firewall not found")
    return result


@router.get(
    "/{asset_id}/firewalls/{engine}/raw",
    response_model=AssetFirewallRawOut,
)
async def get_asset_firewall_raw_policy(
    asset_id: str,
    engine: Literal["firewalld", "ufw", "iptables", "nftables"],
    scope: Literal["runtime", "permanent"] = Query(default="runtime"),
    db: Session = Depends(get_db),
) -> AssetFirewallRawOut:
    result = get_asset_firewall_raw(db, asset_id, engine, scope)
    if result is None:
        raise HTTPException(status_code=404, detail="Asset firewall not found")
    return result


@router.patch("/{asset_id}", response_model=AssetDetail)
async def patch_asset_metadata(
    asset_id: str,
    payload: AssetMetadataUpdate,
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AssetDetail:
    asset = update_asset_metadata(db, asset_id, payload)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.put("/{asset_id}/business-system", response_model=AssetDetail)
async def put_asset_business_system(
    asset_id: str,
    payload: AssetBusinessSystemBinding,
    actor: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> AssetDetail:
    return _run(
        bind_asset_business_system,
        db,
        asset_id,
        payload.business_system_id,
        actor=actor,
    )


def _run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except OwnershipServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        ) from exc
