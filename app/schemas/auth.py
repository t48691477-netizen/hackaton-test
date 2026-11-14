from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


Role = Literal["director", "admin", "dispatcher", "engineer"]
Permission = Literal["scan", "dispatch", "users"]


class AuthLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_key: StrictStr = Field(pattern=r"^[A-HJ-NP-Z2-9]{10}$")

    @field_validator("access_key", mode="before")
    @classmethod
    def normalize_access_key(cls, value: object) -> object:
        if isinstance(value, str):
            if not all(
                char.isspace() or char == "-" or (char.isascii() and char.isalnum())
                for char in value
            ):
                return value
            return "".join(char for char in value.upper() if not char.isspace() and char != "-")
        return value


class AuthAccount(BaseModel):
    id: str
    full_name: str
    email: str
    role: Role
    permissions: list[Permission]


class AuthLoginResponse(BaseModel):
    session_token: str
    expires_at: str
    account: AuthAccount
