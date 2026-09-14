"""HTTP client for the internal Vision Server (/internal/v1/*).

The whole backend uses synchronous SQLAlchemy + boto3, so every route
handler is a plain ``def`` that FastAPI runs in a worker thread. We use a
synchronous ``httpx.Client`` here for the same reason -- it keeps the
request lifecycle (DB session -> S3 -> Vision -> DB commit) simple and
linear without mixing sync/async code paths.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import ValidationError

from core.config import settings
from core.exceptions import AppError
from schemas.vision import VisionPredictResponse

logger = logging.getLogger(__name__)


class VisionNoMainObjectError(Exception):
    """Raised when the Vision Server could not find a central main object.
    Callers must translate this into HTTP 200 RETAKE_REQUIRED (spec 8.1),
    never a 4xx/5xx AppError."""


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.vision_server_base_url,
        timeout=settings.vision_request_timeout_seconds,
    )


def predict(*, image_bytes: bytes, filename: str, content_type: str, request_id: str) -> VisionPredictResponse:
    try:
        with _client() as client:
            response = client.post(
                "/predict",
                files={"image": (filename, image_bytes, content_type)},
                headers={"X-Request-ID": request_id},
            )
    except httpx.ConnectTimeout as exc:
        raise AppError(
            status_code=504,
            code="VISION_TIMEOUT",
            message="이미지 분석 시간이 초과되었습니다. 다시 시도해주세요.",
        ) from exc
    except httpx.TimeoutException as exc:
        raise AppError(
            status_code=504,
            code="VISION_TIMEOUT",
            message="이미지 분석 시간이 초과되었습니다. 다시 시도해주세요.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Vision Server connection error")
        raise AppError(
            status_code=502,
            code="VISION_UNAVAILABLE",
            message="이미지 분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ) from exc

    return _parse_predict_response(response)


def _parse_predict_response(response: httpx.Response) -> VisionPredictResponse:
    if response.status_code == 422:
        body = _safe_json(response)
        if (body or {}).get("code") == "VISION_NO_MAIN_OBJECT":
            raise VisionNoMainObjectError()
        raise AppError(
            status_code=502,
            code="VISION_BAD_RESPONSE",
            message="이미지 분석 결과를 처리할 수 없습니다.",
        )

    if response.status_code == 503:
        raise AppError(
            status_code=503,
            code="VISION_MODEL_NOT_READY",
            message="이미지 분석 모델이 준비되지 않았습니다.",
        )

    if response.status_code in (400, 413, 415):
        body = _safe_json(response) or {}
        code = body.get("code", "INVALID_REQUEST")
        message = body.get("message", "이미지 처리 중 문제가 발생했습니다.")
        status_map = {400: 400, 413: 413, 415: 415}
        raise AppError(status_code=status_map[response.status_code], code=code, message=message)

    if response.status_code != 200:
        logger.error("Vision Server unexpected status=%s body=%s", response.status_code, response.text[:500])
        raise AppError(
            status_code=502,
            code="VISION_BAD_RESPONSE",
            message="이미지 분석 결과를 처리할 수 없습니다.",
        )

    body = _safe_json(response)
    if body is None:
        raise AppError(
            status_code=502,
            code="VISION_BAD_RESPONSE",
            message="이미지 분석 결과를 처리할 수 없습니다.",
        )

    try:
        return VisionPredictResponse.model_validate(body)
    except ValidationError as exc:
        logger.error("Vision Server schema mismatch: %s", exc)
        raise AppError(
            status_code=502,
            code="VISION_BAD_RESPONSE",
            message="이미지 분석 결과를 처리할 수 없습니다.",
        ) from exc


def get_classes() -> dict:
    """Fetch the taxonomy currently loaded by the Vision model. Used for
    optional consistency checks against the backend's waste_classes table
    (not required on the request-handling hot path)."""
    try:
        with _client() as client:
            response = client.get("/classes")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise AppError(
            status_code=502,
            code="VISION_UNAVAILABLE",
            message="이미지 분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ) from exc


def _safe_json(response: httpx.Response) -> dict | None:
    try:
        return response.json()
    except ValueError:
        return None
