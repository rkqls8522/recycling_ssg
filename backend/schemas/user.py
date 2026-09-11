from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import RegionOut


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    region: RegionOut | None = None
    created_at: datetime
    updated_at: datetime


class RegionUpdateRequest(BaseModel):
    region_id: int = Field(gt=0)


class RegionUpdateResponse(BaseModel):
    user_id: int
    region: RegionOut
