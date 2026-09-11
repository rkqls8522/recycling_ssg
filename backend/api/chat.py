"""POST /api/v1/chat (섹션 11). Stateless: nothing is persisted."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent.service import answer_question
from core.database import get_db
from core.deps import get_current_user
from core.exceptions import AppError, user_region_required
from models.feedback import Feedback
from models.user import User
from schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    feedback = db.get(Feedback, payload.feedback_id)
    if feedback is None:
        raise AppError(
            status_code=404,
            code="FEEDBACK_NOT_FOUND",
            message="분석 정보를 찾을 수 없습니다.",
        )
    if feedback.user_id != current_user.user_id:
        raise AppError(
            status_code=403,
            code="FEEDBACK_FORBIDDEN",
            message="해당 분석 정보에 접근할 권한이 없습니다.",
        )
    if current_user.region_id is None:
        raise user_region_required()

    answer, warnings = answer_question(
        db, user=current_user, feedback=feedback, message=payload.message
    )

    return ChatResponse(feedback_id=feedback.feedback_id, answer=answer, warnings=warnings)
