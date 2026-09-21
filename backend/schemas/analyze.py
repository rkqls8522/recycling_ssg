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
    # Top-1(실제 예측) class_id/score. major_category/minor_category와 같은 대상.
    class_id: int
    score: float
    # Top-1을 제외한 "다른 후보" 목록 (모델이 틀렸을 때 사용자에게 보여줄 대안).
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
