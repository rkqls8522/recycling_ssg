"""Shared response schemas used across multiple endpoints (섹션 4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def _to_utc_iso8601(value: datetime) -> str:
    """Serializes datetimes as ``2026-09-11T09:00:00Z`` (섹션 3.3).

    Naive values are assumed to be UTC: everything written by this service
    is stamped with ``models.timestamps.utcnow``, and emitting an explicit
    ``Z`` keeps clients from re-interpreting the value as local time.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


UtcDatetime = Annotated[datetime, PlainSerializer(_to_utc_iso8601, return_type=str)]


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
