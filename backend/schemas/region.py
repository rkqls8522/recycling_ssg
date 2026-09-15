from __future__ import annotations

from pydantic import BaseModel

from schemas.common import RegionOut


class RegionListResponse(BaseModel):
    items: list[RegionOut]
