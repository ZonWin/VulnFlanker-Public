from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.prompts import prompt_template_preview
from app.ai.base import AIMessage
from app.db.models import AICallLog, AIProfile, VulnerabilityAIEnrichment
from app.schemas.ai import AIProfileCreate, AIProfileOut, AIProfileTestResult, AIProfileUpdate
from app.services.ai_completion import complete_json, encode_api_key, hash_ai_request
from app.services.audit import create_audit_log


DEFAULT_TIMEOUT_SECONDS = 30
SUPPORTED_PROVIDERS = {"fake", "openai_compatible"}
SUPPORTED_MODEL_VENDORS = {"openai", "kimi"}
DEFAULT_AI_PROFILE_DEFINITIONS: dict[str, dict[str, object]] = {
    "basic_extraction_profile": {
        "profile_key": "basic_extraction_profile",
        "display_name": "由大模型对已获取的漏洞信息进行进一步结构化提取，对没有标准格式的漏洞信息源效果较佳。",
        "provider": "fake",
        "model_vendor": "openai",
        "base_url": None,
        "api_key_ciphertext": None,
        "model": "fake-json-model",
        "enabled": True,
        "supports_web_search": False,
        "allow_external_network": False,
        "json_mode": True,
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "max_tokens": None,
        "temperature": 0.0,
        "daily_call_limit": None,
        "daily_token_limit": None,
    },
    "web_enrichment_profile": {
        "profile_key": "web_enrichment_profile",
        "display_name": "由大模型结合联网搜索补充漏洞信息，适合本地情报缺少影响版本、修复版本或厂商公告证据时使用。",
        "provider": "fake",
        "model_vendor": "openai",
        "base_url": None,
        "api_key_ciphertext": None,
        "model": "fake-web-model",
        "enabled": True,
        "supports_web_search": True,
        "allow_external_network": False,
        "json_mode": True,
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "max_tokens": None,
        "temperature": 0.0,
        "daily_call_limit": None,
        "daily_token_limit": None,
    },
}


def list_ai_profiles(db: Session) -> list[AIProfileOut]:
    profiles = db.scalars(select(AIProfile).order_by(AIProfile.profile_key)).all()
    return [_to_out(profile) for profile in profiles]


def get_ai_profile(db: Session, profile_id: str) -> AIProfile:
    profile = db.get(AIProfile, profile_id)
    if profile is None:
        raise ValueError("AI profile not found.")
    return profile


def get_or_create_default_ai_profile(db: Session, profile_key: str) -> AIProfile | None:
    normalized_key = _normalize_key(profile_key)
    profile = db.scalar(select(AIProfile).where(AIProfile.profile_key == normalized_key))
    if profile is not None:
        return profile

    defaults = DEFAULT_AI_PROFILE_DEFINITIONS.get(normalized_key)
    if defaults is None:
        return None

    profile = AIProfile(**defaults)
    db.add(profile)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return db.scalar(select(AIProfile).where(AIProfile.profile_key == normalized_key))

    create_audit_log(
        db,
        action="ai_profile.default_created",
        resource_type="ai_profile",
        resource_id=profile.id,
        actor_type="system",
        summary="Created default AI profile.",
        details={
            "profile_key": profile.profile_key,
            "provider": profile.provider,
            "model": profile.model,
            "has_api_key": bool(profile.api_key_ciphertext),
        },
    )
    return profile


def create_ai_profile(
    db: Session,
    payload: AIProfileCreate,
    *,
    actor_id: str | None = None,
    actor_details: dict[str, object | None] | None = None,
) -> AIProfileOut:
    _validate_provider(payload.provider)
    profile = AIProfile(
        profile_key=_normalize_key(payload.profile_key),
        display_name=_normalize_text(payload.display_name, "display_name"),
        provider=payload.provider.strip().lower(),
        model_vendor=_normalize_model_vendor(payload.model_vendor),
        base_url=_normalize_optional_text(payload.base_url),
        api_key_ciphertext=encode_api_key(payload.api_key),
        model=_normalize_text(payload.model, "model"),
        enabled=payload.enabled,
        supports_web_search=payload.supports_web_search,
        allow_external_network=payload.allow_external_network,
        json_mode=payload.json_mode,
        timeout_seconds=payload.timeout_seconds,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
        daily_call_limit=payload.daily_call_limit,
        daily_token_limit=payload.daily_token_limit,
        custom_system_prompt=(
            _normalize_text(payload.prompt_template.system_prompt, "system_prompt")
            if payload.prompt_template
            else None
        ),
        custom_user_prompt_template=(
            _normalize_text(payload.prompt_template.user_prompt_template, "user_prompt_template")
            if payload.prompt_template
            else None
        ),
        custom_output_contract=(
            _normalize_text(payload.prompt_template.output_contract, "output_contract")
            if payload.prompt_template
            else None
        ),
    )
    db.add(profile)
    create_audit_log(
        db,
        action="ai_profile.created",
        resource_type="ai_profile",
        resource_id=profile.id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        summary="Created AI profile.",
        details={
            **(actor_details or {}),
            "profile_key": profile.profile_key,
            "provider": profile.provider,
            "model_vendor": profile.model_vendor,
            "model": profile.model,
            "has_api_key": bool(profile.api_key_ciphertext),
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("AI profile key already exists.") from exc
    db.refresh(profile)
    return _to_out(profile)


def update_ai_profile(
    db: Session,
    profile_id: str,
    payload: AIProfileUpdate,
    *,
    actor_id: str | None = None,
    actor_details: dict[str, object | None] | None = None,
) -> AIProfileOut:
    profile = get_ai_profile(db, profile_id)
    fields = payload.model_fields_set

    if "profile_key" in fields and payload.profile_key is not None:
        profile.profile_key = _normalize_key(payload.profile_key)
    if "display_name" in fields and payload.display_name is not None:
        profile.display_name = _normalize_text(payload.display_name, "display_name")
    if "provider" in fields and payload.provider is not None:
        _validate_provider(payload.provider)
        profile.provider = payload.provider.strip().lower()
    if "model_vendor" in fields and payload.model_vendor is not None:
        profile.model_vendor = _normalize_model_vendor(payload.model_vendor)
    if "base_url" in fields:
        profile.base_url = _normalize_optional_text(payload.base_url)
    if "api_key" in fields:
        profile.api_key_ciphertext = encode_api_key(payload.api_key)
    if "model" in fields and payload.model is not None:
        profile.model = _normalize_text(payload.model, "model")
    if "enabled" in fields and payload.enabled is not None:
        profile.enabled = payload.enabled
    if "supports_web_search" in fields and payload.supports_web_search is not None:
        profile.supports_web_search = payload.supports_web_search
    if "allow_external_network" in fields and payload.allow_external_network is not None:
        profile.allow_external_network = payload.allow_external_network
    if "json_mode" in fields and payload.json_mode is not None:
        profile.json_mode = payload.json_mode
    if "timeout_seconds" in fields and payload.timeout_seconds is not None:
        profile.timeout_seconds = payload.timeout_seconds
    if "max_tokens" in fields:
        profile.max_tokens = payload.max_tokens
    if "temperature" in fields and payload.temperature is not None:
        profile.temperature = payload.temperature
    if "daily_call_limit" in fields:
        profile.daily_call_limit = payload.daily_call_limit
    if "daily_token_limit" in fields:
        profile.daily_token_limit = payload.daily_token_limit
    if "prompt_template" in fields and payload.prompt_template is not None:
        profile.custom_system_prompt = _normalize_text(
            payload.prompt_template.system_prompt,
            "system_prompt",
        )
        profile.custom_user_prompt_template = _normalize_text(
            payload.prompt_template.user_prompt_template,
            "user_prompt_template",
        )
        profile.custom_output_contract = _normalize_text(
            payload.prompt_template.output_contract,
            "output_contract",
        )

    db.add(profile)
    create_audit_log(
        db,
        action="ai_profile.updated",
        resource_type="ai_profile",
        resource_id=profile.id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        summary="Updated AI profile.",
        details={
            **(actor_details or {}),
            "profile_key": profile.profile_key,
            "updated_fields": sorted(fields),
            "model_vendor": profile.model_vendor,
            "has_api_key": bool(profile.api_key_ciphertext),
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("AI profile key already exists.") from exc
    db.refresh(profile)
    return _to_out(profile)


def delete_ai_profile(
    db: Session,
    profile_id: str,
    *,
    actor_id: str | None = None,
    actor_details: dict[str, object | None] | None = None,
) -> AIProfileOut:
    profile = get_ai_profile(db, profile_id)
    deleted = _to_out(profile)

    db.execute(
        update(AICallLog)
        .where(AICallLog.profile_id == profile.id)
        .values(profile_id=None)
    )
    db.execute(
        update(VulnerabilityAIEnrichment)
        .where(VulnerabilityAIEnrichment.profile_id == profile.id)
        .values(profile_id=None)
    )
    create_audit_log(
        db,
        action="ai_profile.deleted",
        resource_type="ai_profile",
        resource_id=profile.id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        summary="Deleted AI profile.",
        details={
            **(actor_details or {}),
            "profile_key": profile.profile_key,
            "display_name": profile.display_name,
            "provider": profile.provider,
            "model_vendor": profile.model_vendor,
            "model": profile.model,
        },
    )
    db.delete(profile)
    db.commit()
    return deleted


def test_ai_profile(
    db: Session,
    profile_id: str,
    *,
    actor_id: str | None = None,
    actor_details: dict[str, object | None] | None = None,
) -> AIProfileTestResult:
    profile = get_ai_profile(db, profile_id)
    request_hash = hash_ai_request(
        {
            "profile_id": profile.id,
            "profile_key": profile.profile_key,
            "purpose": "profile_test",
        }
    )
    result = complete_json(
        db,
        profile,
        messages=[
            AIMessage(
                role="system",
                content="Return a compact JSON object that confirms this AI profile works.",
            ),
            AIMessage(role="user", content='Return {"status":"ok"} as JSON.'),
        ],
        task_type="ai_profile_test",
        target_type="ai_profile",
        target_id=profile.id,
        request_hash=request_hash,
        metadata={"fake_response": {"status": "ok", "profile_key": profile.profile_key}},
    )
    create_audit_log(
        db,
        action="ai_profile.tested",
        resource_type="ai_profile",
        resource_id=profile.id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        outcome="success" if result.status == "success" else "failed",
        summary="Tested AI profile connectivity.",
        details={
            **(actor_details or {}),
            "profile_key": profile.profile_key,
            "provider": profile.provider,
            "model_vendor": profile.model_vendor,
            "model": result.model or profile.model,
            "status": result.status,
        },
    )
    db.commit()
    return AIProfileTestResult(
        success=result.status == "success",
        status=result.status,
        model=result.model or profile.model,
        latency_ms=result.latency_ms,
        error_message=result.error_message,
    )


def _to_out(profile: AIProfile) -> AIProfileOut:
    return AIProfileOut(
        id=profile.id,
        profile_key=profile.profile_key,
        display_name=profile.display_name,
        provider=profile.provider,
        model_vendor=profile.model_vendor,
        base_url=profile.base_url,
        model=profile.model,
        enabled=profile.enabled,
        supports_web_search=profile.supports_web_search,
        allow_external_network=profile.allow_external_network,
        json_mode=profile.json_mode,
        timeout_seconds=profile.timeout_seconds,
        max_tokens=profile.max_tokens,
        temperature=profile.temperature,
        daily_call_limit=profile.daily_call_limit,
        daily_token_limit=profile.daily_token_limit,
        prompt_template=prompt_template_preview(
            profile.profile_key,
            system_prompt=profile.custom_system_prompt,
            user_prompt_template=profile.custom_user_prompt_template,
            output_contract=profile.custom_output_contract,
        ),
        has_api_key=bool(profile.api_key_ciphertext),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _validate_provider(provider: str) -> None:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported AI provider: {provider}")


def _normalize_model_vendor(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_MODEL_VENDORS:
        raise ValueError(f"Unsupported AI model vendor: {value}")
    return normalized


def _normalize_key(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("profile_key cannot be empty.")
    return normalized


def _normalize_text(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} cannot be empty.")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
