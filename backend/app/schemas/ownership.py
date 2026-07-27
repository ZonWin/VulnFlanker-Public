from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


TeamStatus = Literal["active", "inactive"]
PersonStatus = Literal["active", "inactive"]
BusinessSystemStatus = Literal["draft", "active", "inactive"]
SortOrder = Literal["asc", "desc"]

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("email must be a valid email address")
    return normalized


class TeamSummary(BaseModel):
    id: str
    code: str
    name: str
    status: TeamStatus


class ResponsibilityTeamCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)


class ResponsibilityTeamUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)


class ResponsibilityTeamOut(TeamSummary):
    description: str | None = None
    version: int
    person_count: int = 0
    business_system_count: int = 0
    asset_count: int = 0
    created_at: datetime
    updated_at: datetime


class ResponsibilityTeamList(BaseModel):
    items: list[ResponsibilityTeamOut]
    total: int
    page: int
    page_size: int


class TransferMembersRequest(BaseModel):
    person_ids: list[str] = Field(min_length=1, max_length=500)


class PersonSummary(BaseModel):
    id: str
    employee_no: str | None = None
    name: str
    email: str | None = None
    status: PersonStatus
    team: TeamSummary


class PersonCreate(BaseModel):
    employee_no: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    team_id: str = Field(min_length=1, max_length=36)
    user_id: str | None = Field(default=None, max_length=36)
    notes: str | None = Field(default=None, max_length=4000)
    status: PersonStatus = "active"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return _normalize_email(value)


class PersonUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    employee_no: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    team_id: str | None = Field(default=None, min_length=1, max_length=36)
    user_id: str | None = Field(default=None, max_length=36)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return _normalize_email(value)


class PersonOut(PersonSummary):
    phone: str | None = None
    user_id: str | None = None
    notes: str | None = None
    version: int
    business_system_count: int = 0
    asset_count: int = 0
    created_at: datetime
    updated_at: datetime


class PersonList(BaseModel):
    items: list[PersonOut]
    total: int
    page: int
    page_size: int


class PersonDeactivateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    replacement_person_id: str | None = Field(default=None, max_length=36)


class BusinessSystemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    responsible_person_id: str | None = Field(default=None, max_length=36)
    status: Literal["draft", "active"] = "active"


class BusinessSystemUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    responsible_person_id: str | None = Field(default=None, max_length=36)


class BusinessSystemOut(BaseModel):
    id: str
    code: str
    name: str
    description: str | None = None
    responsible_person: PersonSummary | None = None
    status: BusinessSystemStatus
    version: int
    asset_count: int = 0
    created_at: datetime
    updated_at: datetime


class BusinessSystemList(BaseModel):
    items: list[BusinessSystemOut]
    total: int
    page: int
    page_size: int


class BusinessSystemDeactivateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    replacement_system_id: str | None = Field(default=None, max_length=36)
    unassign_assets: bool = False


class VersionedActionRequest(BaseModel):
    expected_version: int = Field(ge=1)


class OwnershipSummary(BaseModel):
    team_count: int
    person_count: int
    business_system_count: int
    asset_count: int
    complete_asset_count: int
    unassigned_asset_count: int
    incomplete_asset_count: int
