from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FavoriteItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    favorite_id: int
    class_id: int
    major_category: str
    minor_category: str
    created_at: datetime


class FavoriteListResponse(BaseModel):
    items: list[FavoriteItemOut]


class FavoriteCreateRequest(BaseModel):
    class_id: int = Field(gt=0)


class FavoriteCreateResponse(BaseModel):
    favorite_id: int
    class_id: int
    major_category: str
    minor_category: str
    message: str = "즐겨찾기에 등록되었습니다."
