from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_current_user
from app.core.config import get_settings
from app.db.models import User
from app.schemas.auth import (
    CurrentUserOut,
    LoginRequest,
    LoginResponse,
    SetupAdminRequest,
    SetupStatusOut,
)
from app.services.auth import (
    authenticate_user,
    create_initial_admin,
    create_user_session,
    ensure_bootstrap_admin,
    has_active_superuser,
    revoke_user_session,
    to_current_user_out,
)

router = APIRouter()


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    settings = get_settings()
    user = authenticate_user(
        db,
        username=payload.username,
        password=payload.password,
        settings=settings,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token, _ = create_user_session(db, user, settings=settings)
    _set_session_cookie(response, token)
    return LoginResponse(user=to_current_user_out(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    revoke_user_session(db, token)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=CurrentUserOut)
async def get_me(
    current_user: User = Depends(require_current_user),
) -> CurrentUserOut:
    return to_current_user_out(current_user)


@router.get("/setup-status", response_model=SetupStatusOut)
async def get_setup_status(db: Session = Depends(get_db)) -> SetupStatusOut:
    ensure_bootstrap_admin(db)
    has_superuser = has_active_superuser(db)
    return SetupStatusOut(
        needs_setup=not has_superuser,
        has_active_superuser=has_superuser,
    )


@router.post(
    "/setup-admin",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
)
async def setup_admin(
    payload: SetupAdminRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    ensure_bootstrap_admin(db)
    if has_active_superuser(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Initial administrator already exists",
        )

    user = create_initial_admin(
        db,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid administrator setup payload",
        )

    token, _ = create_user_session(db, user, settings=get_settings())
    _set_session_cookie(response, token)
    return LoginResponse(user=to_current_user_out(user))
