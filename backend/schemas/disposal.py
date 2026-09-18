from __future__ import annotations

from pydantic import BaseModel

from schemas.common import RegionOut


class DisposalScheduleResponse(BaseModel):
    class_id: int
    major_category: str
    minor_category: str
    region: RegionOut
    disposal_day: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    disposal_method: str | None = None
    source: str = "행정안전부 생활쓰레기배출정보"
