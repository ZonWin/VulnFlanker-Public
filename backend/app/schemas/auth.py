from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=1, max_length=1024)


class SetupAdminRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=8, max_length=1024)
    display_name: str | None = Field(default=None, max_length=255)


class CurrentUserOut(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    is_superuser: bool


class LoginResponse(BaseModel):
    user: CurrentUserOut


class SetupStatusOut(BaseModel):
    needs_setup: bool
    has_active_superuser: bool
