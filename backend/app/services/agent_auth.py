from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.models import AgentAuthEvent, AgentCredential, AgentEnrollmentToken, User
from app.schemas.agent import (
    AgentEnrollIn,
    AgentEnrollOut,
    AgentEnrollmentTokenCreateIn,
    AgentEnrollmentTokenCreateOut,
    AgentEnrollmentTokenOut,
)
from app.services.agent_status import record_agent_heartbeat

ENROLLMENT_TOKEN_BYTES = 32
AGENT_SECRET_BYTES = 48
ENROLLMENT_TOKEN_PREFIX = "vflet_"


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    credential_id: str
    auth_mode: str = "bearer"


def hash_agent_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def mask_enrollment_token(token: str) -> str:
    suffix = token[-4:] if len(token) >= 4 else token
    if token.startswith(ENROLLMENT_TOKEN_PREFIX):
        return f"{ENROLLMENT_TOKEN_PREFIX}***{suffix}"
    return f"***{suffix}"


def public_enrollment_token_preview(token_preview: str | None) -> str | None:
    if token_preview is None:
        return None
    return mask_enrollment_token(token_preview)


def create_enrollment_token(
    db: Session,
    payload: AgentEnrollmentTokenCreateIn,
    *,
    created_by: str | None,
) -> AgentEnrollmentTokenCreateOut:
    token = ENROLLMENT_TOKEN_PREFIX + secrets.token_urlsafe(ENROLLMENT_TOKEN_BYTES)
    row = AgentEnrollmentToken(
        name=payload.name.strip() or "default",
        token_hash=hash_agent_secret(token),
        token_preview=mask_enrollment_token(token),
        expires_at=payload.expires_at,
        max_uses=payload.max_uses,
        used_count=0,
        created_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return AgentEnrollmentTokenCreateOut(
        id=row.id,
        name=row.name,
        enrollment_token=token,
        token_preview=public_enrollment_token_preview(row.token_preview),
        status=_enrollment_token_status(row),
        expires_at=row.expires_at,
        max_uses=row.max_uses,
        used_count=row.used_count,
        created_by=row.created_by,
        created_by_display=_user_display_name(db.get(User, row.created_by)) if row.created_by else None,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_enrollment_tokens(db: Session) -> list[AgentEnrollmentTokenOut]:
    rows = db.execute(
        select(AgentEnrollmentToken, User)
        .outerjoin(User, AgentEnrollmentToken.created_by == User.id)
        .order_by(
            AgentEnrollmentToken.created_at.desc(),
            AgentEnrollmentToken.name.asc(),
        )
    ).all()
    return [_enrollment_token_out(row, user) for row, user in rows]


def revoke_enrollment_token(db: Session, token_id: str) -> AgentEnrollmentTokenOut | None:
    row = db.get(AgentEnrollmentToken, token_id)
    if row is None:
        return None
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        db.add(row)
        db.commit()
        db.refresh(row)
    user = db.get(User, row.created_by) if row.created_by else None
    return _enrollment_token_out(row, user)


def enroll_agent(db: Session, payload: AgentEnrollIn) -> AgentEnrollOut | None:
    enrollment = _valid_enrollment_token(db, payload.enrollment_token)
    if enrollment is None:
        record_agent_auth_event(
            db,
            event_type="enroll_failed",
            agent_id=payload.agent_id,
            reason="invalid_enrollment_token",
        )
        db.commit()
        return None

    agent_id = payload.agent_id or _new_agent_id()
    secret = "vflas_" + secrets.token_urlsafe(AGENT_SECRET_BYTES)
    credential = AgentCredential(
        agent_id=agent_id,
        secret_hash=hash_agent_secret(secret),
        secret_version=1,
        status="active",
    )
    enrollment.used_count += 1
    db.add(credential)
    record_agent_heartbeat(
        db,
        payload=_heartbeat_from_enroll(payload, agent_id),
    )
    record_agent_auth_event(
        db,
        event_type="enrolled",
        agent_id=agent_id,
        reason=f"enrollment_token_id={enrollment.id}",
    )
    db.commit()
    return AgentEnrollOut(
        agent_id=agent_id,
        agent_secret=secret,
        agent_api_prefix=get_settings().agent_api_prefix,
    )


def authenticate_agent_secret(db: Session, secret: str | None) -> AgentIdentity | None:
    if not secret:
        return None
    credential = db.scalar(
        select(AgentCredential).where(
            AgentCredential.secret_hash == hash_agent_secret(secret),
        )
    )
    if credential is None or not _credential_is_active(credential):
        return None
    credential.last_used_at = utcnow()
    db.add(credential)
    return AgentIdentity(agent_id=credential.agent_id, credential_id=credential.id)


def record_agent_auth_event(
    db: Session,
    *,
    event_type: str,
    agent_id: str | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        AgentAuthEvent(
            agent_id=agent_id,
            event_type=event_type,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )


def _valid_enrollment_token(db: Session, token: str) -> AgentEnrollmentToken | None:
    row = db.scalar(
        select(AgentEnrollmentToken).where(
            AgentEnrollmentToken.token_hash == hash_agent_secret(token),
        )
    )
    if row is None or row.revoked_at is not None:
        return None
    now = utcnow()
    if row.expires_at is not None and _ensure_aware(row.expires_at) <= now:
        return None
    if row.max_uses is not None and row.used_count >= row.max_uses:
        return None
    return row


def _enrollment_token_out(
    row: AgentEnrollmentToken,
    created_by_user: User | None = None,
) -> AgentEnrollmentTokenOut:
    return AgentEnrollmentTokenOut(
        id=row.id,
        name=row.name,
        token_preview=public_enrollment_token_preview(row.token_preview),
        status=_enrollment_token_status(row),
        expires_at=row.expires_at,
        max_uses=row.max_uses,
        used_count=row.used_count,
        created_by=row.created_by,
        created_by_display=_user_display_name(created_by_user),
        revoked_at=row.revoked_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _user_display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.display_name or user.username or user.id


def _enrollment_token_status(row: AgentEnrollmentToken) -> str:
    if row.revoked_at is not None:
        return "revoked"
    now = utcnow()
    if row.expires_at is not None and _ensure_aware(row.expires_at) <= now:
        return "expired"
    if row.max_uses is not None and row.used_count >= row.max_uses:
        return "used_up"
    return "active"


def _credential_is_active(credential: AgentCredential) -> bool:
    if credential.status != "active" or credential.revoked_at is not None:
        return False
    if credential.expires_at is not None and _ensure_aware(credential.expires_at) <= utcnow():
        return False
    return True


def _new_agent_id() -> str:
    return "vf-agent-" + secrets.token_hex(16)


def _heartbeat_from_enroll(payload: AgentEnrollIn, agent_id: str):
    from app.schemas.agent import AgentHeartbeatIn

    return AgentHeartbeatIn(
        agent_id=agent_id,
        hostname=payload.hostname,
        platform=payload.platform,
        version=payload.version,
    )


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
