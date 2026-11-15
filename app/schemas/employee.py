from uuid import UUID

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.schemas.auth import Role


class EmployeeResponse(BaseModel):
    """Public employee profile returned by the users API."""

    id: UUID
    full_name: str
    email: str
    role: Role


class EmployeeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: StrictStr = Field(min_length=1, max_length=120)
    email: StrictStr = Field(min_length=3, max_length=254)
    role: Literal["admin", "dispatcher", "engineer"]

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if "\r" in value or "\n" in value:
                raise ValueError("full_name must be a single line")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().lower()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                raise ValueError("email is invalid")
        return value


class EmployeeInvitationResponse(BaseModel):
    status: Literal["not_sent", "sent", "failed"]
    provider: Literal["smtp", "gmail", "mock"] | None
    email: str
    sent_at: str | None = None


class EmployeeProvisionResponse(BaseModel):
    account: EmployeeResponse
    invitation: EmployeeInvitationResponse
