from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Asset, BusinessSystem, Person, ResponsibilityTeam
from app.services.audit import create_audit_log


@dataclass
class OwnershipMigrationReport:
    created_team_count: int = 0
    created_person_count: int = 0
    created_system_count: int = 0
    bound_asset_count: int = 0
    unassigned_asset_count: int = 0
    conflicting_system_count: int = 0
    conflict_samples: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def migrate_legacy_asset_ownership(
    db: Session,
    *,
    commit: bool = True,
) -> OwnershipMigrationReport:
    report = OwnershipMigrationReport()
    assets = list(
        db.scalars(
            select(Asset)
            .where(Asset.business_system_id.is_(None))
            .order_by(Asset.id)
        ).all()
    )
    groups: dict[str, list[Asset]] = defaultdict(list)
    for asset in assets:
        system_key = normalize_legacy_value(asset.business_system)
        if system_key is None:
            report.unassigned_asset_count += 1
            continue
        groups[system_key].append(asset)

    for system_key, grouped_assets in groups.items():
        combinations = {
            (
                normalize_legacy_value(asset.owner_team),
                normalize_legacy_value(asset.owner_person),
            )
            for asset in grouped_assets
        }
        resolved_people: dict[tuple[str | None, str | None], Person | None] = {}
        for team_key, person_key in combinations:
            resolved_people[(team_key, person_key)] = _resolve_legacy_person(
                db,
                grouped_assets,
                team_key=team_key,
                person_key=person_key,
                report=report,
            )

        complete_combinations = [
            combination
            for combination, person in resolved_people.items()
            if person is not None
        ]
        is_conflict = len(combinations) > 1
        if is_conflict:
            report.conflicting_system_count += 1
            if len(report.conflict_samples) < 20:
                report.conflict_samples.append(
                    {
                        "business_system": grouped_assets[0].business_system,
                        "asset_ids": [asset.id for asset in grouped_assets[:10]],
                        "owner_combinations": [
                            {"team": team, "person": person}
                            for team, person in sorted(
                                combinations,
                                key=lambda item: (item[0] or "", item[1] or ""),
                            )
                        ],
                    }
                )

        system = db.scalar(
            select(BusinessSystem).where(BusinessSystem.normalized_name == system_key)
        )
        if system is None:
            display_name = _clean_display(grouped_assets[0].business_system) or system_key
            responsible_person = (
                resolved_people[complete_combinations[0]]
                if len(combinations) == 1 and len(complete_combinations) == 1
                else None
            )
            system = BusinessSystem(
                code=_legacy_code("SYS", system_key),
                name=display_name,
                normalized_name=system_key,
                description="由资产历史运营归属文本归一化创建。",
                responsible_person=responsible_person,
                status="active" if responsible_person is not None else "draft",
            )
            db.add(system)
            db.flush()
            report.created_system_count += 1

        for asset in grouped_assets:
            asset.business_system_record = system
            asset.ownership_source = "migration"
            asset.ownership_updated_at = utcnow()
            report.bound_asset_count += 1

    create_audit_log(
        db,
        action="ownership.asset.bulk_assigned",
        resource_type="ownership_migration",
        actor_type="system",
        summary="Normalized legacy asset ownership text into structured relationships.",
        details={**report.to_dict(), "source": "migration"},
    )
    if commit:
        db.commit()
    else:
        db.flush()
        db.rollback()
    return report


def normalize_legacy_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()
    return normalized or None


def _resolve_legacy_person(
    db: Session,
    assets: list[Asset],
    *,
    team_key: str | None,
    person_key: str | None,
    report: OwnershipMigrationReport,
) -> Person | None:
    if team_key is None or person_key is None:
        return None
    sample = next(
        asset
        for asset in assets
        if normalize_legacy_value(asset.owner_team) == team_key
        and normalize_legacy_value(asset.owner_person) == person_key
    )
    team = db.scalar(
        select(ResponsibilityTeam).where(
            ResponsibilityTeam.normalized_name == team_key
        )
    )
    if team is None:
        team = ResponsibilityTeam(
            code=_legacy_code("TEAM", team_key),
            name=_clean_display(sample.owner_team) or team_key,
            normalized_name=team_key,
            description="由资产历史运营归属文本归一化创建。",
            status="active",
        )
        db.add(team)
        db.flush()
        report.created_team_count += 1

    people = list(db.scalars(select(Person).where(Person.team_id == team.id)).all())
    person = next(
        (candidate for candidate in people if normalize_legacy_value(candidate.name) == person_key),
        None,
    )
    if person is None:
        person = Person(
            name=_clean_display(sample.owner_person) or person_key,
            team=team,
            notes="由资产历史运营归属文本归一化创建。",
            status="active",
        )
        db.add(person)
        db.flush()
        report.created_person_count += 1
    return person


def _clean_display(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    return normalized or None


def _legacy_code(prefix: str, normalized_value: str) -> str:
    digest = hashlib.sha1(
        normalized_value.encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()[:12].upper()
    return f"LEGACY-{prefix}-{digest}"
