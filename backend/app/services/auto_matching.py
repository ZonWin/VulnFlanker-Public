from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.matching import VulnerabilityNotReadyForMatching, evaluate_matches
from app.services.platform_settings import get_platform_settings


def maybe_auto_match_new_asset(db: Session, asset_id: str) -> int:
    settings = get_platform_settings(db)
    if not settings.auto_match_on_new_asset:
        return 0
    return _run_auto_match(db, asset_id=asset_id)


def maybe_auto_match_new_vulnerability(db: Session, vulnerability_id: str) -> int:
    settings = get_platform_settings(db)
    if not settings.auto_match_on_new_vulnerability:
        return 0
    return _run_auto_match(db, vulnerability_id=vulnerability_id)


def _run_auto_match(
    db: Session,
    *,
    asset_id: str | None = None,
    vulnerability_id: str | None = None,
) -> int:
    try:
        results = evaluate_matches(
            db,
            asset_id=asset_id,
            vulnerability_id=vulnerability_id,
            raise_if_vulnerability_blocked=False,
            trigger_type="automatic",
        )
    except VulnerabilityNotReadyForMatching:
        return 0
    except Exception:
        db.rollback()
        return 0
    return len(results)
