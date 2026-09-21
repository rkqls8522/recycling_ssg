from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from schemas.common import CandidateScoreOut, RegionOut


class NationalRuleOut(BaseModel):
    source: str
    method: str | None = None


class RegionRuleOut(BaseModel):
    region: str
    source_url: str
    exception_type: str
    method: str


class AnalyzeSuccessResponse(BaseModel):
    status: Literal["SUCCESS"] = "SUCCESS"
    major_category: str
    minor_category: str
    candidate_scores: list[CandidateScoreOut]
    user_region: RegionOut
    disposal_day: str | None = None
    national_rule: NationalRuleOut | None = None
    region_rule: RegionRuleOut | None = None
    image_id: int
    feedback_id: int
    warnings: list[str] = []


class AnalyzeRetakeResponse(BaseModel):
    status: Literal["RETAKE_REQUIRED"] = "RETAKE_REQUIRED"
    code: Literal["AI_LOW_CONFIDENCE", "AI_NO_MAIN_OBJECT"]
    message: str
    threshold: float | None = None
    # AI_LOW_CONFIDENCE일 때 실제 Top-1 신뢰도 점수 (threshold 미만이라 재촬영을
    # 요구한 바로 그 값). AI_NO_MAIN_OBJECT는 애초에 점수를 낼 대상이 없으므로 null.
    score: float | None = None
    request_id: str
