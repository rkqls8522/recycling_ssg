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
