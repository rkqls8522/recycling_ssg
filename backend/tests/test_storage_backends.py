"""services/storage.py dispatch + the local filesystem backend.

The local backend exists so the whole stack can run without AWS
credentials; it must preserve the exact s3_key semantics of the real S3
backend (섹션 15.2: DB 에는 s3_key 만 저장).
"""

from __future__ import annotations

import pytest

from core.config import settings
from core.exceptions import AppError
from services import local_storage, s3_service, storage


@pytest.fixture
def local_backend(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    return tmp_path


def test_storage_dispatches_to_selected_backend(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    assert storage._backend() is local_storage

    monkeypatch.setattr(settings, "storage_backend", "s3")
    assert storage._backend() is s3_service

    # Unknown/misspelled values fall back to the production backend.
    monkeypatch.setattr(settings, "storage_backend", "S3")
    assert storage._backend() is s3_service


def test_local_round_trip_preserves_key_semantics(local_backend):
    key = storage.upload_image(
        file_bytes=b"\xff\xd8\xff\xe0jpeg-bytes",
        content_type="image/jpeg",
        user_id=101,
        extension="jpg",
    )

    # Same key shape as the S3 backend: feedback/YYYY/MM/DD/<user>-<uuid>.jpg
    assert key.startswith("feedback/")
    assert key.endswith(".jpg")
    assert "101-" in key
    assert not key.startswith("/") and "://" not in key  # a key, not a URL

    assert (local_backend / key).is_file()
    assert storage.download_image(key) == b"\xff\xd8\xff\xe0jpeg-bytes"

    storage.delete_object(key)
    assert not (local_backend / key).exists()


def test_local_delete_is_idempotent(local_backend):
    storage.delete_object("feedback/2026/09/12/does-not-exist.jpg")  # must not raise


def test_local_download_missing_key_maps_to_spec_error(local_backend):
    with pytest.raises(AppError) as exc_info:
        storage.download_image("feedback/2026/09/12/missing.jpg")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "S3_DOWNLOAD_FAILED"


def test_local_backend_refuses_path_traversal(local_backend):
    with pytest.raises(AppError) as exc_info:
        local_storage.download_image("../../../../etc/passwd")

    assert exc_info.value.code in {"S3_UPLOAD_FAILED", "S3_DOWNLOAD_FAILED"}
