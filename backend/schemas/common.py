"""Shared response schemas used across multiple endpoints (섹션 4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from models.timestamps import KST


def _to_utc_iso8601(value: datetime) -> str:
    """Serializes datetimes as ``2026-09-11T09:00:00Z`` (섹션 3.3).

    Naive values are assumed to be KST: everything written by this service
    (including mock data inserted directly via SQL, which falls back to
    MySQL's own ``NOW()`` -- see core/database.py's session timezone) is
    stamped as KST (``models.timestamps.now_kst``) so it reads correctly at
    a glance in a MySQL client. The API contract itself is unaffected --
    this still converts to real UTC and emits an explicit ``Z`` so clients
    never have to guess the wire format.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=KST)
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
