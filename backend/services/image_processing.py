"""Resize + re-encode uploaded images before they reach Vision/S3.

Why this exists: a phone photo can easily be 4000×3000px / 8MB+. Neither
the Vision Server nor S3 need the full-resolution original -- YOLO resizes
internally to its own training resolution anyway (well under 1920px), and
storing the full original just costs more S3 storage/egress for no benefit.

So every upload is, once:
  1. Decoded with Pillow (this is also where a mislabeled/corrupt file is
     now caught as IMAGE_DECODE_FAILED, instead of relying on the Vision
     Server's own decode step -- fails faster, one less network hop).
  2. EXIF-orientation corrected (a phone photo taken "sideways" carries a
     rotation flag rather than pre-rotated pixels; without this the stored
     image would visually appear rotated).
  3. Downscaled so neither side exceeds ``settings.image_max_dimension``,
     preserving aspect ratio. Never upscaled.
  4. Re-encoded to a compact, consistent format (JPEG by default, WEBP
     optional via ``IMAGE_OUTPUT_FORMAT``).

The SAME processed bytes are then sent to both the Vision Server and S3,
so the stored image is exactly what Vision analyzed (bbox stays a valid
0~1 normalized rectangle on the stored image either way).
"""

from __future__ import annotations

import io
import logging

from PIL import Image as PILImage
from PIL import ImageOps, UnidentifiedImageError

from core.config import settings
from core.exceptions import AppError

logger = logging.getLogger(__name__)

_CONTENT_TYPE_BY_FORMAT = {
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
_EXTENSION_BY_FORMAT = {
    "jpeg": "jpg",
    "webp": "webp",
}


def _decode_failed() -> AppError:
    return AppError(
        status_code=400,
        code="IMAGE_DECODE_FAILED",
        message="이미지를 읽을 수 없습니다. 다른 이미지를 사용해주세요.",
    )


def _flatten_to_rgb(img: PILImage.Image) -> PILImage.Image:
    """JPEG has no alpha channel; composite any transparency onto white
    instead of silently converting it to black."""
    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    if has_alpha:
        rgba = img.convert("RGBA")
        background = PILImage.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def process_upload(raw_bytes: bytes) -> tuple[bytes, str, str]:
    """Decodes, resizes and re-encodes an uploaded image.

    Returns ``(processed_bytes, content_type, extension)``. Raises
    :class:`AppError` with code ``IMAGE_DECODE_FAILED`` (섹션 8.1) if
    Pillow cannot decode ``raw_bytes`` as an image at all.
    """
    try:
        with PILImage.open(io.BytesIO(raw_bytes)) as opened:
            opened.load()  # Image.open() is lazy; force the actual decode now.
            img = ImageOps.exif_transpose(opened) or opened
            img = _flatten_to_rgb(img)

            max_dim = settings.image_max_dimension
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), PILImage.Resampling.LANCZOS)

            output_format = (
                "webp" if settings.image_output_format.lower() == "webp" else "jpeg"
            )
            buffer = io.BytesIO()
            if output_format == "webp":
                img.save(buffer, format="WEBP", quality=settings.image_output_quality, method=6)
            else:
                img.save(
                    buffer,
                    format="JPEG",
                    quality=settings.image_output_quality,
                    optimize=True,
                )
    except UnidentifiedImageError as exc:
        raise _decode_failed() from exc
    except OSError as exc:
        # Truncated/corrupt files often surface here instead of as
        # UnidentifiedImageError (which only covers "no matching decoder").
        logger.warning("image decode failed: %s", exc)
        raise _decode_failed() from exc

    processed_bytes = buffer.getvalue()
    if not processed_bytes:
        raise _decode_failed()

    return (
        processed_bytes,
        _CONTENT_TYPE_BY_FORMAT[output_format],
        _EXTENSION_BY_FORMAT[output_format],
    )
