"""Filesystem-backed stand-in for S3, for local development only.

Mirrors the s3_service interface exactly and keeps the same ``s3_key``
semantics (the key is the path relative to ``local_storage_dir``), so the
API behaviour and everything stored in the DB are identical to running
against real S3. Selected with ``STORAGE_BACKEND=local``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.config import settings
from core.exceptions import AppError

logger = logging.getLogger(__name__)


def _root() -> Path:
    return Path(settings.local_storage_dir).resolve()


def _resolve(key: str) -> Path:
    """Resolves a key under the storage root, refusing path traversal."""
    root = _root()
    target = (root / key).resolve()
    if not target.is_relative_to(root):
        raise AppError(
            status_code=502,
            code="S3_UPLOAD_FAILED",
            message="이미지 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        )
    return target


def upload_image(*, file_bytes: bytes, content_type: str, user_id: int, extension: str) -> str:
    from services.s3_service import build_object_key

    key = build_object_key(user_id, extension)
    target = _resolve(key)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)
    except OSError as exc:
        logger.exception("local storage write failed key=%s", key)
        raise AppError(
            status_code=502,
            code="S3_UPLOAD_FAILED",
            message="이미지 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        ) from exc
    return key


def download_image(key: str) -> bytes:
    target = _resolve(key)
    try:
        return target.read_bytes()
    except OSError as exc:
        logger.exception("local storage read failed key=%s", key)
        raise AppError(
            status_code=502,
            code="S3_DOWNLOAD_FAILED",
            message="원본 이미지를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.",
        ) from exc


def delete_object(key: str) -> None:
    """Best-effort compensating delete; never raises (mirrors s3_service)."""
    try:
        _resolve(key).unlink(missing_ok=True)
    except Exception:
        logger.exception("local storage compensating delete failed key=%s", key)
