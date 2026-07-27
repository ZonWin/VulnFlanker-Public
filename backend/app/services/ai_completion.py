from __future__ import annotations

import hashlib
import json
from base64 import b64decode, urlsafe_b64encode
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.base import AICompletionRequest, AICompletionResult, AIMessage
from app.ai.providers import build_provider_client
from app.core.config import Settings, get_settings
from app.db.models import AICallLog, AIProfile

ENCRYPTED_API_KEY_PREFIX = "fernet:"
LEGACY_B64_API_KEY_PREFIX = "b64:"
LEGACY_PLAIN_API_KEY_PREFIX = "plain:"


def complete_json(
    db: Session,
    profile: AIProfile,
    *,
    messages: list[AIMessage],
    task_type: str,
    target_type: str = "unknown",
    target_id: str | None = None,
    request_hash: str | None = None,
    allow_web_search: bool = False,
    metadata: dict[str, Any] | None = None,
) -> AICompletionResult:
    request_hash = request_hash or hash_ai_request(
        {
            "profile_id": profile.id,
            "model": profile.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "allow_web_search": allow_web_search,
            "metadata": metadata or {},
        }
    )
    started = perf_counter()
    limit_error = _profile_limit_error(db, profile)
    if limit_error:
        result = AICompletionResult(
            status="failed",
            model=profile.model,
            error_message=limit_error,
        )
    else:
        try:
            client = build_provider_client(profile.provider)
            result = client.complete_json(
                AICompletionRequest(
                    provider=profile.provider,
                    model_vendor=profile.model_vendor,
                    base_url=profile.base_url,
                    api_key=decode_api_key(profile.api_key_ciphertext),
                    model=profile.model,
                    messages=messages,
                    json_mode=profile.json_mode,
                    timeout_seconds=profile.timeout_seconds,
                    max_tokens=profile.max_tokens,
                    temperature=profile.temperature,
                    allow_web_search=allow_web_search,
                    metadata=metadata or {},
                )
            )
        except Exception as exc:
            result = AICompletionResult(
                status="failed",
                model=profile.model,
                error_message=str(exc),
            )

    result.latency_ms = int((perf_counter() - started) * 1000)
    db.add(
        AICallLog(
            profile_id=profile.id,
            task_type=task_type,
            target_type=target_type,
            target_id=target_id,
            request_hash=request_hash,
            model=result.model or profile.model,
            status=result.status,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            latency_ms=result.latency_ms,
            error_message=result.error_message,
        )
    )
    db.flush()
    return result


def _profile_limit_error(db: Session, profile: AIProfile) -> str | None:
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    if profile.daily_call_limit is not None:
        call_count = db.scalar(
            select(func.count(AICallLog.id)).where(
                AICallLog.profile_id == profile.id,
                AICallLog.created_at >= since,
                AICallLog.status.in_(("success", "timeout", "failed")),
            )
        ) or 0
        if call_count >= profile.daily_call_limit:
            return "AI profile daily call limit exceeded."

    if profile.daily_token_limit is not None:
        token_count = db.scalar(
            select(func.coalesce(func.sum(AICallLog.total_tokens), 0)).where(
                AICallLog.profile_id == profile.id,
                AICallLog.created_at >= since,
            )
        ) or 0
        if token_count >= profile.daily_token_limit:
            return "AI profile daily token limit exceeded."
    return None


def hash_ai_request(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def encode_api_key(
    api_key: str | None,
    *,
    settings: Settings | None = None,
) -> str | None:
    if api_key is None:
        return None
    stripped = api_key.strip()
    if not stripped:
        return None
    fernet = _api_key_fernet(settings or get_settings())
    encrypted = fernet.encrypt(stripped.encode("utf-8")).decode("ascii")
    return ENCRYPTED_API_KEY_PREFIX + encrypted


def decode_api_key(
    api_key_ciphertext: str | None,
    *,
    settings: Settings | None = None,
) -> str | None:
    if not api_key_ciphertext:
        return None
    if api_key_ciphertext.startswith(ENCRYPTED_API_KEY_PREFIX):
        token = api_key_ciphertext.removeprefix(ENCRYPTED_API_KEY_PREFIX)
        try:
            return _api_key_fernet(settings or get_settings()).decrypt(
                token.encode("ascii")
            ).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError(
                "Stored AI API key could not be decrypted with the current "
                "VULNFLANKER_AI_KEY_ENCRYPTION_KEY."
            ) from exc
    if api_key_ciphertext.startswith(LEGACY_B64_API_KEY_PREFIX):
        return b64decode(
            api_key_ciphertext.removeprefix(LEGACY_B64_API_KEY_PREFIX)
        ).decode("utf-8")
    if api_key_ciphertext.startswith(LEGACY_PLAIN_API_KEY_PREFIX):
        return api_key_ciphertext.removeprefix(LEGACY_PLAIN_API_KEY_PREFIX)
    return api_key_ciphertext


def _api_key_fernet(settings: Settings) -> Fernet:
    secret = (settings.ai_key_encryption_key or "").strip()
    if not secret:
        raise ValueError(
            "VULNFLANKER_AI_KEY_ENCRYPTION_KEY is required to save or decrypt "
            "AI API keys."
        )
    key = urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)
