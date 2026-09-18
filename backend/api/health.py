"""GET /health, GET /ready (섹션 14.1, 14.2). No auth, no /api/v1 prefix."""

from __future__ import annotations

from fastapi import APIRouter

from core.database import check_db_connection
from core.exceptions import AppError
from schemas.health import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="backend")


@router.get("/ready", response_model=ReadyResponse)
def readiness_check() -> ReadyResponse:
    db_ok = check_db_connection()
    if not db_ok:
        raise AppError(
            status_code=503,
            code="SERVICE_NOT_READY",
            message="서비스 준비가 완료되지 않았습니다.",
        )
    return ReadyResponse(status="ready", database=True)
