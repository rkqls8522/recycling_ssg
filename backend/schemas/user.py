from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import RegionOut, UtcDatetime


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    region: RegionOut | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class RegionUpdateRequest(BaseModel):
    region_id: int = Field(gt=0)


class RegionUpdateResponse(BaseModel):
    user_id: int
    region: RegionOut
