"""Gemini-backed Vision Fallback (섹션 9.3) and free-text generation used by
the stateless AI Agent (섹션 11).

Uses the current ``google-genai`` SDK (the older ``google-generativeai``
package is deprecated). Raises generic ``Gemini*Error`` exceptions rather
than ``AppError`` directly, because the two call sites
(feedback.not_in_list vs. chat) map failures to different spec error codes
(GEMINI_* vs. AGENT_*).
"""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from core.config import settings
from models.waste_class import WasteClass

logger = logging.getLogger(__name__)


class GeminiNotConfiguredError(Exception):
    pass


class GeminiUnavailableError(Exception):
    pass


class GeminiTimeoutError(Exception):
    pass


class GeminiBadResponseError(Exception):
    pass


def _client(timeout_seconds: float) -> genai.Client:
    if not settings.gemini_api_key:
        raise GeminiNotConfiguredError
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=genai_types.HttpOptions(timeout=int(timeout_seconds * 1000)),
    )


def reanalyze_image(
    *, image_bytes: bytes, mime_type: str, allowed_classes: list[WasteClass]
) -> int:
    """Sends the original image back to Gemini and asks it to pick the best
    matching class_id from the service's own taxonomy. Returns the chosen
    class_id, guaranteed to be one of ``allowed_classes``."""
    client = _client(settings.gemini_vision_timeout_seconds)

    catalog = "\n".join(
        f"{c.class_id}: {c.major_category}/{c.minor_category}" for c in allowed_classes
    )
    prompt = (
        "너는 생활폐기물 분리배출 분류를 돕는 비전 분석기다.\n"
        "아래 이미지에 있는 폐기물과 가장 일치하는 항목을 다음 class 목록에서 "
        "정확히 하나 선택해라. 목록의 class_id 외의 값은 사용할 수 없다.\n\n"
        f"{catalog}\n\n"
        '반드시 다음 JSON 형식으로만 답하라: {"class_id": <정수>}'
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model_name,
            contents=[
                prompt,
                genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ],
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except genai_errors.ClientError as exc:
        if _is_timeout(exc):
            raise GeminiTimeoutError from exc
        logger.exception("Gemini vision fallback client error")
        raise GeminiUnavailableError from exc
    except genai_errors.ServerError as exc:
        logger.exception("Gemini vision fallback server error")
        raise GeminiUnavailableError from exc
    except TimeoutError as exc:
        raise GeminiTimeoutError from exc
    except Exception as exc:
        logger.exception("Gemini vision fallback unexpected error")
        raise GeminiUnavailableError from exc

    class_id = _parse_class_id(response.text)
    allowed_ids = {c.class_id for c in allowed_classes}
    if class_id not in allowed_ids:
        raise GeminiBadResponseError(f"class_id {class_id} not in allowed taxonomy")
    return class_id


def _parse_class_id(raw_text: str | None) -> int:
    if not raw_text:
        raise GeminiBadResponseError("empty response")
    try:
        data = json.loads(raw_text)
        return int(data["class_id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise GeminiBadResponseError(f"could not parse class_id from: {raw_text!r}") from exc


def generate_text(prompt: str) -> str:
    """Generic free-text generation used by the AI Agent chat endpoint."""
    client = _client(settings.gemini_chat_timeout_seconds)
    try:
        response = client.models.generate_content(
            model=settings.gemini_model_name,
            contents=prompt,
        )
    except genai_errors.ClientError as exc:
        if _is_timeout(exc):
            raise GeminiTimeoutError from exc
        logger.exception("Gemini chat client error")
        raise GeminiUnavailableError from exc
    except genai_errors.ServerError as exc:
        logger.exception("Gemini chat server error")
        raise GeminiUnavailableError from exc
    except TimeoutError as exc:
        raise GeminiTimeoutError from exc
    except Exception as exc:
        logger.exception("Gemini chat unexpected error")
        raise GeminiUnavailableError from exc

    if not response.text:
        raise GeminiBadResponseError("empty chat response")
    return response.text.strip()


def _is_timeout(exc: genai_errors.APIError) -> bool:
    code = getattr(exc, "code", None)
    return code == 408 or "timeout" in str(exc).lower() or "deadline" in str(exc).lower()
