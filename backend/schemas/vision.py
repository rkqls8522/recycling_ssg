"""Typed shape of the Vision Server's /internal/v1/predict response, used
only for internal parsing/validation inside services/vision_client.py."""

from __future__ import annotations

from pydantic import BaseModel

from schemas.common import CandidateScoreOut


class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class InternalMeta(BaseModel):
    bbox: BBox
    model_version: str
    inference_ms: float


class VisionPredictResponse(BaseModel):
    major_category: str
    minor_category: str
    candidate_scores: list[CandidateScoreOut]
    internal_meta: InternalMeta
