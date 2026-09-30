from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.analyze import NationalRuleOut, RegionRuleOut


class ConfirmResponse(BaseModel):
    feedback_id: int
    is_correct: Literal[True] = True
    final_class_id: int
    correction_source: None = None
    message: str = "분석 결과가 맞는 것으로 저장되었습니다."


class SelectCandidateRequest(BaseModel):
    class_id: int = Field(gt=0)


class SelectCandidateResponse(BaseModel):
    feedback_id: int
    is_correct: Literal[False] = False
    final_class_id: int
    correction_source: Literal["USER"] = "USER"
    message: str = "선택한 객체 후보로 수정되었습니다."


class NotInListResponse(BaseModel):
    feedback_id: int
    is_correct: Literal[False] = False
    final_class_id: int
    correction_source: Literal["GEMINI"] = "GEMINI"
    major_category: str
    minor_category: str
    disposal_day: str | None = None
    national_rule: NationalRuleOut | None = None
    region_rule: RegionRuleOut | None = None
    message: str = "추가 이미지 분석 결과로 수정되었습니다."


class NotInListRetakeResponse(BaseModel):
    """RAG 재분류 그래프가 judge 검증을 통과하지 못하고 재시도 횟수를
    소진했을 때(handle_not_in_list 의 needs_retake=True) 반환된다."""

    status: Literal["RETAKE_REQUIRED"] = "RETAKE_REQUIRED"
    code: Literal["AI_RECLASSIFY_FAILED"] = "AI_RECLASSIFY_FAILED"
    message: str = "재분류에 실패했습니다. 사진을 다시 촬영해 업로드해주세요."
