from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.agent_auth import AgentIdentity, authenticate_agent_secret, record_agent_auth_event


def get_agent_identity(
    request: Request,
    db: Session = Depends(get_db),
) -> AgentIdentity | None:
    secret = _bearer_token(request.headers.get("authorization"))
    identity = authenticate_agent_secret(db, secret)
    if identity is None and secret:
        record_agent_auth_event(
            db,
            event_type="auth_failed",
            reason="invalid_bearer_token",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
    return identity


def require_agent_identity(
    identity: AgentIdentity | None = Depends(get_agent_identity),
) -> AgentIdentity:
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent authentication required",
        )
    return identity


def _bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()
