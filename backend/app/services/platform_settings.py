from __future__ import annotations

import base64
import re

from sqlalchemy.orm import Session

from app.db.models import PlatformSettings
from app.schemas.platform_settings import PlatformSettingsOut, PlatformSettingsUpdate
from app.services.audit import create_audit_log


PLATFORM_SETTINGS_ID = "default"
DEFAULT_PLATFORM_NAME = "VulnFlanker"
DEFAULT_PLATFORM_SUBTITLE = "漏洞监测平台"
AI_AUTO_ACCEPT_POLICY_STRICT = "strict"
AI_AUTO_ACCEPT_POLICY_MODERATE = "moderate"
AI_AUTO_ACCEPT_POLICY_RELAXED = "relaxed"
DEFAULT_AI_AUTO_ACCEPT_POLICY = AI_AUTO_ACCEPT_POLICY_MODERATE
DEFAULT_AI_AUTO_ACCEPT_CONFIDENCE = 0.85
DEFAULT_AI_WEB_AUTO_ACCEPT_CONFIDENCE = 0.8
DEFAULT_AI_LAYER2_DAILY_LIMIT = 50
DEFAULT_AI_BATCH_MAX_SIZE = 100
MAX_LOGO_BYTES = 300 * 1024

_LOGO_DATA_URL_PATTERN = re.compile(
    r"^data:image/(png|jpe?g|webp|gif|svg\+xml);base64,",
    re.IGNORECASE,
)


def get_platform_settings(db: Session) -> PlatformSettings:
    settings = db.get(PlatformSettings, PLATFORM_SETTINGS_ID)
    if settings is not None:
        return settings

    settings = PlatformSettings(
        id=PLATFORM_SETTINGS_ID,
        platform_name=DEFAULT_PLATFORM_NAME,
        platform_subtitle=DEFAULT_PLATFORM_SUBTITLE,
        logo_data_url=None,
        ai_enabled=True,
        ai_auto_enrich_enabled=False,
        ai_auto_accept_enabled=False,
        ai_auto_accept_policy=DEFAULT_AI_AUTO_ACCEPT_POLICY,
        ai_auto_accept_confidence=DEFAULT_AI_AUTO_ACCEPT_CONFIDENCE,
        ai_web_auto_accept_confidence=DEFAULT_AI_WEB_AUTO_ACCEPT_CONFIDENCE,
        ai_layer2_daily_limit=DEFAULT_AI_LAYER2_DAILY_LIMIT,
        ai_batch_max_size=DEFAULT_AI_BATCH_MAX_SIZE,
        ai_allow_web_enrichment_default=False,
        auto_match_on_new_asset=False,
        auto_match_on_new_vulnerability=False,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def is_product_only_matching_enabled(settings: PlatformSettings) -> bool:
    return settings.ai_auto_accept_policy == AI_AUTO_ACCEPT_POLICY_RELAXED


def get_platform_settings_out(db: Session) -> PlatformSettingsOut:
    return _to_out(get_platform_settings(db))


def update_platform_settings(
    db: Session,
    update: PlatformSettingsUpdate,
    *,
    actor_id: str | None = None,
    actor_details: dict[str, object | None] | None = None,
) -> PlatformSettingsOut:
    settings = get_platform_settings(db)
    fields = update.model_fields_set

    if "platform_name" in fields:
        settings.platform_name = _normalize_text(
            update.platform_name,
            default=DEFAULT_PLATFORM_NAME,
            max_length=80,
            label="platform_name",
        )
    if "platform_subtitle" in fields:
        settings.platform_subtitle = _normalize_text(
            update.platform_subtitle,
            default=DEFAULT_PLATFORM_SUBTITLE,
            max_length=120,
            label="platform_subtitle",
        )
    if "logo_data_url" in fields:
        settings.logo_data_url = _normalize_logo_data_url(update.logo_data_url)
    if "ai_enabled" in fields and update.ai_enabled is not None:
        settings.ai_enabled = update.ai_enabled
    if "ai_auto_enrich_enabled" in fields and update.ai_auto_enrich_enabled is not None:
        settings.ai_auto_enrich_enabled = update.ai_auto_enrich_enabled
    if "ai_auto_accept_enabled" in fields and update.ai_auto_accept_enabled is not None:
        settings.ai_auto_accept_enabled = update.ai_auto_accept_enabled
    if "ai_auto_accept_policy" in fields and update.ai_auto_accept_policy is not None:
        settings.ai_auto_accept_policy = update.ai_auto_accept_policy
    if (
        "ai_auto_accept_confidence" in fields
        and update.ai_auto_accept_confidence is not None
    ):
        settings.ai_auto_accept_confidence = update.ai_auto_accept_confidence
    if (
        "ai_web_auto_accept_confidence" in fields
        and update.ai_web_auto_accept_confidence is not None
    ):
        settings.ai_web_auto_accept_confidence = update.ai_web_auto_accept_confidence
    if "ai_layer2_daily_limit" in fields and update.ai_layer2_daily_limit is not None:
        settings.ai_layer2_daily_limit = update.ai_layer2_daily_limit
    if "ai_batch_max_size" in fields and update.ai_batch_max_size is not None:
        settings.ai_batch_max_size = update.ai_batch_max_size
    if (
        "ai_allow_web_enrichment_default" in fields
        and update.ai_allow_web_enrichment_default is not None
    ):
        settings.ai_allow_web_enrichment_default = update.ai_allow_web_enrichment_default
    if "auto_match_on_new_asset" in fields and update.auto_match_on_new_asset is not None:
        settings.auto_match_on_new_asset = update.auto_match_on_new_asset
    if (
        "auto_match_on_new_vulnerability" in fields
        and update.auto_match_on_new_vulnerability is not None
    ):
        settings.auto_match_on_new_vulnerability = update.auto_match_on_new_vulnerability

    db.add(settings)
    create_audit_log(
        db,
        action="platform_settings.updated",
        resource_type="platform_settings",
        resource_id=settings.id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        outcome="success",
        summary="Updated platform branding settings.",
        details={
            **(actor_details or {}),
            "updated_fields": sorted(fields),
            "has_custom_logo": bool(settings.logo_data_url),
            "ai_enabled": settings.ai_enabled,
            "ai_auto_enrich_enabled": settings.ai_auto_enrich_enabled,
            "ai_auto_accept_enabled": settings.ai_auto_accept_enabled,
            "auto_match_on_new_asset": settings.auto_match_on_new_asset,
            "auto_match_on_new_vulnerability": settings.auto_match_on_new_vulnerability,
        },
    )
    db.commit()
    db.refresh(settings)
    return _to_out(settings)


def reset_platform_settings(
    db: Session,
    *,
    actor_id: str | None = None,
    actor_details: dict[str, object | None] | None = None,
) -> PlatformSettingsOut:
    settings = get_platform_settings(db)
    settings.platform_name = DEFAULT_PLATFORM_NAME
    settings.platform_subtitle = DEFAULT_PLATFORM_SUBTITLE
    settings.logo_data_url = None

    db.add(settings)
    create_audit_log(
        db,
        action="platform_settings.reset",
        resource_type="platform_settings",
        resource_id=settings.id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        outcome="success",
        summary="Reset platform branding settings to defaults.",
        details=actor_details or {},
    )
    db.commit()
    db.refresh(settings)
    return _to_out(settings)


def _normalize_text(
    value: str | None,
    *,
    default: str,
    max_length: int,
    label: str,
) -> str:
    if value is None:
        return default
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} cannot be empty.")
    if len(normalized) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    return normalized


def _normalize_logo_data_url(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    match = _LOGO_DATA_URL_PATTERN.match(normalized)
    if match is None:
        raise ValueError(
            "logo_data_url must be a base64 data URL for png, jpg, webp, gif, or svg."
        )

    encoded = normalized[match.end() :]
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError("logo_data_url contains invalid base64 data.") from exc

    if len(decoded) > MAX_LOGO_BYTES:
        raise ValueError("logo_data_url image must be 300 KB or smaller.")
    return normalized


def _to_out(settings: PlatformSettings) -> PlatformSettingsOut:
    return PlatformSettingsOut(
        id=settings.id,
        platform_name=settings.platform_name or DEFAULT_PLATFORM_NAME,
        platform_subtitle=settings.platform_subtitle or DEFAULT_PLATFORM_SUBTITLE,
        logo_data_url=settings.logo_data_url,
        ai_enabled=settings.ai_enabled,
        ai_auto_enrich_enabled=settings.ai_auto_enrich_enabled,
        ai_auto_accept_enabled=settings.ai_auto_accept_enabled,
        ai_auto_accept_policy=settings.ai_auto_accept_policy
        or DEFAULT_AI_AUTO_ACCEPT_POLICY,
        ai_auto_accept_confidence=settings.ai_auto_accept_confidence,
        ai_web_auto_accept_confidence=settings.ai_web_auto_accept_confidence,
        ai_layer2_daily_limit=settings.ai_layer2_daily_limit,
        ai_batch_max_size=settings.ai_batch_max_size,
        ai_allow_web_enrichment_default=settings.ai_allow_web_enrichment_default,
        auto_match_on_new_asset=settings.auto_match_on_new_asset,
        auto_match_on_new_vulnerability=settings.auto_match_on_new_vulnerability,
        updated_at=settings.updated_at,
    )
