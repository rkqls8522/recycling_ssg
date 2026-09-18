"""Vision Server error type + exception handlers, mirroring the Backend's
ErrorResponse contract (섹션 4.1) so the Backend's vision_client can parse
failures uniformly."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

REQUEST_ID_HEADER = "X-Request-ID"


class VisionError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def _body(code: str, message: str, request_id: str) -> dict:
    return {
        "success": False,
        "code": code,
        "message": message,
        "details": None,
        "request_id": request_id,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(VisionError)
    async def vision_error_handler(request: Request, exc: VisionError) -> JSONResponse:
        request_id = _request_id(request)
        response = JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, request_id),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = _request_id(request)
        response = JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_body("REQUEST_VALIDATION_ERROR", "요청 값이 올바르지 않습니다.", request_id),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = _request_id(request)
        response = JSONResponse(
            status_code=exc.status_code,
            content=_body("INVALID_REQUEST", str(exc.detail), request_id),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_body("VISION_INFERENCE_ERROR", "이미지 분석 중 오류가 발생했습니다.", request_id),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
