"""Response schemas for /internal/v1/* (섹션 13)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    success: bool = False
    code: str
    message: str
    details: Any | None = None
    request_id: str


class CandidateScoreOut(BaseModel):
    class_id: int
    category: str
    score: float


class BBoxOut(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class InternalMetaOut(BaseModel):
    bbox: BBoxOut
    model_version: str
    inference_ms: float


class PredictResponse(BaseModel):
    major_category: str
    minor_category: str
    # Top-1(실제 예측) class_id/score. major_category/minor_category와 같은 대상.
    class_id: int
    score: float
    # Top-1을 제외한 "다른 후보" 목록 (모델이 틀렸을 때 사용자에게 보여줄 대안).
    # score 내림차순, 최대 TOP_K - 1개.
    candidate_scores: list[CandidateScoreOut]
    internal_meta: InternalMetaOut


class ClassEntryOut(BaseModel):
    class_id: int
    major_category: str
    minor_category: str


class ClassesResponse(BaseModel):
    model_version: str
    classes: list[ClassEntryOut]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str | None = None
