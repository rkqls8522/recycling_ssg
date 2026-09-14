"""AWS S3 image storage.

Only ``images.s3_key`` is ever persisted to the DB (섹션 15.2) — never a
presigned URL. Uploads happen only after the Vision Top-1 score passes the
confidence threshold; if the DB transaction that follows fails, the caller
is expected to call :func:`delete_object` as a compensating action.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from botocore.exceptions import ConnectionError as BotoConnectionError

from core.config import settings
from core.exceptions import AppError

logger = logging.getLogger(__name__)


def _client():
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.aws_s3_endpoint_url,
        config=BotoConfig(
            connect_timeout=settings.s3_request_timeout_seconds,
            read_timeout=settings.s3_request_timeout_seconds,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def build_object_key(user_id: int, extension: str) -> str:
    now = datetime.now(UTC)
    return f"feedback/{now:%Y/%m/%d}/{user_id}-{uuid.uuid4().hex}.{extension.lstrip('.')}"


def upload_image(*, file_bytes: bytes, content_type: str, user_id: int, extension: str) -> str:
    """Uploads raw image bytes and returns the resulting S3 object key."""
    key = build_object_key(user_id, extension)
    try:
        _client().put_object(
            Bucket=settings.aws_s3_bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
    except BotoConnectionError as exc:
        logger.exception("S3 upload timeout/connection error key=%s", key)
        raise AppError(
            status_code=504,
            code="S3_TIMEOUT",
            message="이미지 저장 시간이 초과되었습니다. 다시 시도해주세요.",
        ) from exc
    except (ClientError, BotoCoreError) as exc:
        logger.exception("S3 upload failed key=%s", key)
        raise AppError(
            status_code=502,
            code="S3_UPLOAD_FAILED",
            message="이미지 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        ) from exc
    return key


def delete_object(key: str) -> None:
    """Best-effort compensating delete. Never raises — failures are logged
    only, since this runs after we've already decided to fail the request
    for another reason (DB transaction failure)."""
    try:
        _client().delete_object(Bucket=settings.aws_s3_bucket, Key=key)
    except Exception:
        logger.exception("S3 compensating delete failed key=%s", key)


def download_image(key: str) -> bytes:
    try:
        obj = _client().get_object(Bucket=settings.aws_s3_bucket, Key=key)
        return obj["Body"].read()
    except BotoConnectionError as exc:
        raise AppError(
            status_code=504,
            code="S3_TIMEOUT",
            message="이미지 저장 시간이 초과되었습니다. 다시 시도해주세요.",
        ) from exc
    except (ClientError, BotoCoreError) as exc:
        logger.exception("S3 download failed key=%s", key)
        raise AppError(
            status_code=502,
            code="S3_DOWNLOAD_FAILED",
            message="원본 이미지를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.",
        ) from exc
