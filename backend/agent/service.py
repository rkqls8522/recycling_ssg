"""Stateless AI Agent used by POST /api/v1/chat (섹션 11).

No conversation is persisted (chat_sessions/chat_messages are intentionally
absent from the schema, spec 섹션 1/2). Each call rebuilds context from the
current ``feedback`` row + region, then asks the RAG 서비스의 챗봇 노드
(node4)에 national_rule/region_rule을 근거로 한 답변을 요청한다. RAG 서비스가
죽어있거나 지역 정보가 없으면, 같은 컨텍스트로 만든 결정적 템플릿 답변으로
대체해 챗봇 기능 자체는 항상 응답하도록 한다 (구 Gemini 미설정 폴백과 동일한
설계를 RAG 장애까지 확장).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from agent.tools import retrieve_tips
from core.exceptions import AppError
from models.feedback import Feedback
from models.region import Region
from models.user import User
from models.waste_class import WasteClass
from services.disposal_service import get_chat_answer_or_warn, get_disposal_info_or_warn

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
    if region is not None:
        disposal_day, disposal_warnings = get_disposal_info_or_warn(waste_class, region)
        warnings.extend(disposal_warnings)

    tips = retrieve_tips(waste_class.major_category)

    answer: str | None = None
    if region is not None:
        answer, chat_warnings = get_chat_answer_or_warn(
            message=message,
            major_category=waste_class.major_category,
            minor_category=waste_class.minor_category,
            user_region={
                "region_id": region.region_id,
                "sido_name": region.sido_name,
                "sgg_name": region.sgg_name,
            },
        )
        warnings.extend(chat_warnings)

    if answer is None:
        logger.info("chat RAG service unavailable or no region, using deterministic fallback")
        answer = _fallback_answer(
            major_category=waste_class.major_category,
            minor_category=waste_class.minor_category,
            disposal_day=disposal_day,
            tips=tips,
        )

    return answer, warnings
