"""Stateless AI Agent used by POST /api/v1/chat (섹션 11).

No conversation is persisted (chat_sessions/chat_messages are intentionally
absent from the schema, spec 섹션 1/2). Each call rebuilds context from the
current ``feedback`` row + region + a small retrieval ("RAG") step, then
asks Gemini for a natural-language answer. If Gemini is not configured we
still answer, using a deterministic template built from the same context,
so the feature keeps working in environments without an LLM key.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from agent.prompts import build_chat_prompt
from agent.tools import retrieve_tips
from core.exceptions import AppError
from models.feedback import Feedback
from models.region import Region
from models.user import User
from models.waste_class import WasteClass
from services import gemini_service
from services.disposal_service import get_disposal_info_or_warn

logger = logging.getLogger(__name__)


def _current_class(db: Session, feedback: Feedback) -> WasteClass:
    class_id = feedback.final_class_id or feedback.predicted_class_id
    waste_class = db.get(WasteClass, class_id)
    if waste_class is None:
        raise AppError(
            status_code=404,
            code="CLASS_NOT_FOUND",
            message="폐기물 분류 정보를 찾을 수 없습니다.",
        )
    return waste_class


def _fallback_answer(
    *, major_category: str, minor_category: str, disposal_day: str | None, tips: list[str]
) -> str:
    day_text = f"배출요일은 {disposal_day}입니다." if disposal_day else "배출요일 정보를 확인할 수 없습니다."
    tips_text = " ".join(tips[:2])
    return (
        f"분석된 품목은 {major_category}/{minor_category}입니다. {day_text} "
        f"{tips_text} 자세한 사항은 지역 분리배출 안내를 함께 확인해주세요."
    )


def answer_question(db: Session, *, user: User, feedback: Feedback, message: str) -> tuple[str, list[str]]:
    warnings: list[str] = []

    waste_class = _current_class(db, feedback)

    region: Region | None = user.region
    disposal_day: str | None = None
    disposal_method: str | None = None
    if region is not None:
        disposal_day, disposal_warnings = get_disposal_info_or_warn(waste_class, region)
        warnings.extend(disposal_warnings)

    tips = retrieve_tips(waste_class.major_category)

    sido_name = region.sido_name if region else ""
    sgg_name = region.sgg_name if region else ""

    try:
        prompt = build_chat_prompt(
            major_category=waste_class.major_category,
            minor_category=waste_class.minor_category,
            sido_name=sido_name,
            sgg_name=sgg_name,
            disposal_day=disposal_day,
            disposal_method=disposal_method,
            tips=tips,
            user_message=message,
        )
        answer = gemini_service.generate_text(prompt)
        return answer, warnings
    except gemini_service.GeminiNotConfiguredError:
        logger.info("Gemini not configured, using deterministic chat fallback")
        return (
            _fallback_answer(
                major_category=waste_class.major_category,
                minor_category=waste_class.minor_category,
                disposal_day=disposal_day,
                tips=tips,
            ),
            warnings,
        )
    except gemini_service.GeminiTimeoutError as exc:
        raise AppError(
            status_code=504,
            code="AGENT_TIMEOUT",
            message="AI 안내 응답 시간이 초과되었습니다. 다시 시도해주세요.",
        ) from exc
    except (gemini_service.GeminiUnavailableError, gemini_service.GeminiBadResponseError) as exc:
        raise AppError(
            status_code=502,
            code="AGENT_UNAVAILABLE",
            message="AI 안내 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ) from exc
