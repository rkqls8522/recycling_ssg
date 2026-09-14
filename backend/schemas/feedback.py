from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
    message: str = "추가 이미지 분석 결과로 수정되었습니다."
