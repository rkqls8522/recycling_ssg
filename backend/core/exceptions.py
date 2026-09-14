"""Central application error type + exception handlers.

Every handled error in this service is raised as an ``AppError`` and turned
into the common ``ErrorResponse`` contract (success/code/message/details/
request_id) defined in the API spec (섹션 4.1, 16).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class AppError(Exception):
    """Raise this anywhere in the request lifecycle to produce a spec-compliant
    HTTP error response."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


# --- Convenience factories for the most common, reused errors -------------


def auth_required() -> AppError:
    return AppError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="AUTH_REQUIRED",
        message="로그인이 필요합니다.",
    )


def auth_token_invalid() -> AppError:
    return AppError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="AUTH_TOKEN_INVALID",
        message="유효하지 않은 로그인 정보입니다.",
    )


def auth_token_expired() -> AppError:
    return AppError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="AUTH_TOKEN_EXPIRED",
        message="로그인이 만료되었습니다. 다시 로그인해주세요.",
    )


def user_not_found() -> AppError:
    return AppError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="USER_NOT_FOUND",
        message="사용자 정보를 찾을 수 없습니다.",
    )


def user_region_required(message: str = "먼저 거주 지역을 선택해주세요.") -> AppError:
    return AppError(
        status_code=status.HTTP_409_CONFLICT,
        code="USER_REGION_REQUIRED",
        message=message,
    )


def database_error() -> AppError:
    return AppError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DATABASE_ERROR",
        message="데이터베이스 처리 중 오류가 발생했습니다.",
    )


def internal_server_error() -> AppError:
    return AppError(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="서버 내부 오류가 발생했습니다.",
    )


def validation_error(
    details: list[dict[str, str]] | None = None,
    message: str = "요청 값이 올바르지 않습니다.",
) -> AppError:
    """``message`` defaults to the section-16 catalog string, but some
    endpoints pin their own wording for REQUEST_VALIDATION_ERROR (e.g.
    GET /api/v1/regions in 섹션 7.2), so it is overridable."""
    return AppError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="REQUEST_VALIDATION_ERROR",
        message=message,
        details=details,
    )


def _error_body(*, code: str, message: str, details: Any, request_id: str) -> dict:
    return {
        "success": False,
        "code": code,
        "message": message,
        "details": details,
        "request_id": request_id,
    }


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = _request_id(request)
        response = JSONResponse(
            status_code=exc.status_code,
            content=_error_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=request_id,
            ),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _request_id(request)
        details = [
            {
                "field": ".".join(str(p) for p in err["loc"] if p != "body"),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        response = JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body(
                code="REQUEST_VALIDATION_ERROR",
                message="요청 값이 올바르지 않습니다.",
                details=details,
                request_id=request_id,
            ),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = _request_id(request)
        code = "AUTH_REQUIRED" if exc.status_code == 401 else "INVALID_REQUEST"
        message = (
            exc.detail
            if isinstance(exc.detail, str) and exc.status_code not in (404,)
            else "요청하신 리소스를 찾을 수 없습니다."
            if exc.status_code == 404
            else "잘못된 요청입니다."
        )
        response = JSONResponse(
            status_code=exc.status_code,
            content=_error_body(
                code=code, message=message, details=None, request_id=request_id
            ),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        """Safety net so a DB failure always surfaces as 503 DATABASE_ERROR.

        Endpoints still catch SQLAlchemyError locally where they need to roll
        back or run a compensating action; this only guarantees that any path
        we did not wrap (e.g. a read executed before the try block) still
        honours the contract instead of leaking a 500.
        """
        request_id = _request_id(request)
        logger.exception("unhandled database error on %s %s", request.method, request.url.path)
        response = JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error_body(
                code="DATABASE_ERROR",
                message="데이터베이스 처리 중 오류가 발생했습니다.",
                details=None,
                request_id=request_id,
            ),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = _request_id(request)
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                code="INTERNAL_SERVER_ERROR",
                message="서버 내부 오류가 발생했습니다.",
                details=jsonable_encoder({"error": str(exc)})
                if app.debug
                else None,
                request_id=request_id,
            ),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
