from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from schemas.common import CandidateScoreOut, RegionOut


class AnalyzeSuccessResponse(BaseModel):
    status: Literal["SUCCESS"] = "SUCCESS"
    major_category: str
    minor_category: str
    candidate_scores: list[CandidateScoreOut]
    user_region: RegionOut
    disposal_day: str | None = None
    image_id: int
    feedback_id: int
    warnings: list[str] = []


class AnalyzeRetakeResponse(BaseModel):
    status: Literal["RETAKE_REQUIRED"] = "RETAKE_REQUIRED"
    code: Literal["AI_LOW_CONFIDENCE", "AI_NO_MAIN_OBJECT"]
    message: str
    threshold: float | None = None
    request_id: str
