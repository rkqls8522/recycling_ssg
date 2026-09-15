from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from schemas.common import RegionOut, UtcDatetime
from schemas.user import UserProfileOut


class SignupRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_byte_length(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("비밀번호는 최대 72바이트까지 허용됩니다.")
        return v


class SignupResponse(BaseModel):
    user_id: int
    email: str
    region: RegionOut | None = None
    created_at: UtcDatetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileOut
