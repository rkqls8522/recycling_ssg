from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import UtcDatetime


class FavoriteItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    favorite_id: int
    class_id: int
    major_category: str
    minor_category: str
    created_at: UtcDatetime


class FavoriteListResponse(BaseModel):
    items: list[FavoriteItemOut]


class FavoriteCreateRequest(BaseModel):
    class_id: int = Field(ge=0)


class FavoriteCreateResponse(BaseModel):
    favorite_id: int
    class_id: int
    major_category: str
    minor_category: str
    message: str = "즐겨찾기에 등록되었습니다."
