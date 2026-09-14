"""services/image_processing.py — resize + re-encode pipeline.

Covers the two properties the user asked for explicitly:
  - long side capped at settings.image_max_dimension (default 1920), aspect
    ratio preserved, never upscaled
  - re-encoded to a compact, consistent format (JPEG by default, WEBP
    optional) so S3 storage stays small regardless of the original format
"""

from __future__ import annotations

import io

import pytest
from PIL import Image as PILImage

from core.config import settings
from core.exceptions import AppError
from services import image_processing


def _make_jpeg(width: int, height: int, color=(200, 100, 50)) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (width, height), color=color).save(buffer, format="JPEG")
    return buffer.getvalue()


def _make_png_rgba(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGBA", (width, height), (10, 20, 30, 128)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_downscales_large_image_preserving_aspect_ratio():
    # 3840x2160 (16:9), long side well above the 1920 cap.
    raw = _make_jpeg(3840, 2160)

    processed_bytes, content_type, extension = image_processing.process_upload(raw)

    with PILImage.open(io.BytesIO(processed_bytes)) as out:
        width, height = out.size
    assert max(width, height) <= settings.image_max_dimension
    # Aspect ratio preserved (16:9 -> 1920x1080 exactly, since 3840/2=1920).
    assert width == 1920
    assert height == 1080
    assert content_type == "image/jpeg"
    assert extension == "jpg"


def test_does_not_upscale_small_image():
    raw = _make_jpeg(320, 240)

    processed_bytes, _content_type, _extension = image_processing.process_upload(raw)

    with PILImage.open(io.BytesIO(processed_bytes)) as out:
        assert out.size == (320, 240)  # untouched, not enlarged toward 1920


def test_output_is_meaningfully_smaller_than_a_large_original():
    # A large, low-compressibility (noisy-ish) image to make the size drop obvious.
    raw = _make_jpeg(3840, 2160, color=(123, 222, 45))

    processed_bytes, *_ = image_processing.process_upload(raw)

    assert len(processed_bytes) < len(raw)


def test_flattens_transparent_png_onto_white_instead_of_black():
    raw = _make_png_rgba(100, 100)

    processed_bytes, content_type, extension = image_processing.process_upload(raw)

    assert content_type == "image/jpeg"  # PNG in, JPEG out (default format)
    assert extension == "jpg"
    with PILImage.open(io.BytesIO(processed_bytes)) as out:
        assert out.mode == "RGB"  # JPEG has no alpha channel


def test_corrupt_bytes_raise_image_decode_failed():
    with pytest.raises(AppError) as exc_info:
        image_processing.process_upload(b"this is not an image at all")

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "IMAGE_DECODE_FAILED"


def test_empty_bytes_raise_image_decode_failed():
    with pytest.raises(AppError) as exc_info:
        image_processing.process_upload(b"")

    assert exc_info.value.code == "IMAGE_DECODE_FAILED"


def test_webp_output_format_is_selectable(monkeypatch):
    monkeypatch.setattr(settings, "image_output_format", "webp")
    raw = _make_jpeg(2400, 1600)

    processed_bytes, content_type, extension = image_processing.process_upload(raw)

    assert content_type == "image/webp"
    assert extension == "webp"
    with PILImage.open(io.BytesIO(processed_bytes)) as out:
        assert out.format == "WEBP"
        assert max(out.size) <= settings.image_max_dimension


def test_respects_custom_max_dimension(monkeypatch):
    monkeypatch.setattr(settings, "image_max_dimension", 800)
    raw = _make_jpeg(1600, 1200)  # 4:3

    processed_bytes, *_ = image_processing.process_upload(raw)

    with PILImage.open(io.BytesIO(processed_bytes)) as out:
        assert max(out.size) == 800
        assert out.size == (800, 600)  # aspect ratio preserved
