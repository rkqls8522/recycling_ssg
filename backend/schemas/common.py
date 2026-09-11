"""Shared response schemas used across multiple endpoints (섹션 4)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    code: str
    message: str
    details: Any | None = None
    request_id: str


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region_id: int
    sido_name: str
    sgg_name: str


class CandidateScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    class_id: int
    category: str = Field(description="예: 플라스틱류_욕실용품")
    score: float
