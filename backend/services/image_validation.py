"""Shared multipart image validation used by POST /api/v1/analyze."""

from __future__ import annotations

from fastapi import UploadFile

from core.config import settings
from core.exceptions import AppError

_EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def validate_and_read(file: UploadFile) -> tuple[bytes, str, str]:
    """Returns (file_bytes, content_type, extension). Raises AppError for
    every failure case defined in 섹션 8.1's 오류 응답 table."""
    content_type = (file.content_type or "").lower()
    if content_type not in settings.allowed_image_content_type_set:
        raise AppError(
            status_code=415,
            code="IMAGE_TYPE_UNSUPPORTED",
            message="지원하지 않는 이미지 형식입니다. JPG, PNG 또는 WEBP 이미지를 사용해주세요.",
        )

    file_bytes = file.file.read()

    if not file_bytes:
        raise AppError(
            status_code=400,
            code="IMAGE_EMPTY",
            message="업로드된 이미지가 비어 있습니다.",
        )

    if len(file_bytes) > settings.max_image_size_bytes:
        raise AppError(
            status_code=413,
            code="IMAGE_TOO_LARGE",
            message="업로드 가능한 이미지 크기를 초과했습니다.",
        )

    extension = _EXTENSION_BY_CONTENT_TYPE.get(content_type, "jpg")
    return file_bytes, content_type, extension
