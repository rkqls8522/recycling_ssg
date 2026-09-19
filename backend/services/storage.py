"""Storage facade used by the API layer.

Dispatches to real AWS S3 (production, 섹션 15.2) or to the local
filesystem stand-in, based on ``settings.storage_backend``. Both backends
expose the same three operations and the same ``s3_key`` semantics, so
``images.s3_key`` means the same thing either way and nothing else in the
codebase needs to know which one is active.
"""

from __future__ import annotations

from core.config import settings
from services import local_storage, s3_service


def _backend():
    return local_storage if settings.storage_backend.lower() == "local" else s3_service


def upload_image(*, file_bytes: bytes, content_type: str, user_id: int, extension: str) -> str:
    return _backend().upload_image(
        file_bytes=file_bytes,
        content_type=content_type,
        user_id=user_id,
        extension=extension,
    )


def download_image(key: str) -> bytes:
    return _backend().download_image(key)


def delete_object(key: str) -> None:
    _backend().delete_object(key)
