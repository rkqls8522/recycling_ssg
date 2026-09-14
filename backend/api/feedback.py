"""POST /api/v1/feedback/{feedback_id}/confirm, /select-candidate,
/not-in-list (섹션 9)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from core.exceptions import AppError, database_error
from models.feedback import Feedback
from models.feedback_candidate import FeedbackCandidate
from models.image import Image
from models.user import User
from models.waste_class import WasteClass
from schemas.feedback import (
    ConfirmResponse,
    NotInListResponse,
    SelectCandidateRequest,
    SelectCandidateResponse,
)
from services import gemini_service, storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


def _load_owned_feedback(db: Session, feedback_id: int, user: User) -> Feedback:
    feedback = db.get(Feedback, feedback_id)
    if feedback is None:
        raise AppError(
            status_code=404,
            code="FEEDBACK_NOT_FOUND",
            message="피드백 정보를 찾을 수 없습니다.",
        )
    if feedback.user_id != user.user_id:
        raise AppError(
            status_code=403,
            code="FEEDBACK_FORBIDDEN",
            message="해당 피드백에 접근할 권한이 없습니다.",
        )
    if feedback.is_completed:
        raise AppError(
            status_code=409,
            code="FEEDBACK_ALREADY_COMPLETED",
            message="이미 처리된 피드백입니다.",
        )
    return feedback


def _commit(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("feedback update DB error")
        raise database_error() from exc


@router.post("/{feedback_id}/confirm", response_model=ConfirmResponse)
def confirm_feedback(
    feedback_id: int = Path(gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConfirmResponse:
    feedback = _load_owned_feedback(db, feedback_id, current_user)

    feedback.final_class_id = feedback.predicted_class_id
    feedback.is_correct = True
    feedback.correction_source = None
    _commit(db)

    return ConfirmResponse(feedback_id=feedback.feedback_id, final_class_id=feedback.final_class_id)


@router.post("/{feedback_id}/select-candidate", response_model=SelectCandidateResponse)
def select_candidate(
    payload: SelectCandidateRequest,
    feedback_id: int = Path(gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SelectCandidateResponse:
    feedback = _load_owned_feedback(db, feedback_id, current_user)

    if payload.class_id == feedback.predicted_class_id:
        raise AppError(
            status_code=400,
            code="FEEDBACK_SAME_AS_PREDICTION",
            message="최초 분석 결과와 같은 후보입니다. 맞다고 확인해주세요.",
        )

    is_valid_candidate = (
        db.query(FeedbackCandidate)
        .filter(
            FeedbackCandidate.feedback_id == feedback.feedback_id,
            FeedbackCandidate.class_id == payload.class_id,
        )
        .first()
        is not None
    )
    if not is_valid_candidate:
        raise AppError(
            status_code=400,
            code="FEEDBACK_INVALID_CANDIDATE",
            message="선택한 객체 후보가 해당 분석 결과에 존재하지 않습니다.",
        )

    feedback.final_class_id = payload.class_id
    feedback.is_correct = False
    feedback.correction_source = "USER"
    _commit(db)

    return SelectCandidateResponse(feedback_id=feedback.feedback_id, final_class_id=feedback.final_class_id)


@router.post("/{feedback_id}/not-in-list", response_model=NotInListResponse)
def not_in_list(
    feedback_id: int = Path(gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotInListResponse:
    feedback = _load_owned_feedback(db, feedback_id, current_user)

    image = db.get(Image, feedback.image_id)
    if image is None:
        raise AppError(
            status_code=404,
            code="FEEDBACK_NOT_FOUND",
            message="피드백 정보를 찾을 수 없습니다.",
        )

    image_bytes = storage.download_image(image.s3_key)
    allowed_classes = db.query(WasteClass).all()

    try:
        final_class_id = gemini_service.reanalyze_image(
            image_bytes=image_bytes,
            mime_type=image.content_type,
            allowed_classes=allowed_classes,
        )
    except gemini_service.GeminiNotConfiguredError as exc:
        raise AppError(
            status_code=503,
            code="GEMINI_NOT_CONFIGURED",
            message="추가 이미지 분석 서비스가 설정되지 않았습니다.",
        ) from exc
    except gemini_service.GeminiTimeoutError as exc:
        raise AppError(
            status_code=504,
            code="GEMINI_TIMEOUT",
            message="추가 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요.",
        ) from exc
    except gemini_service.GeminiBadResponseError as exc:
        raise AppError(
            status_code=502,
            code="GEMINI_BAD_RESPONSE",
            message="추가 이미지 분석 결과를 처리할 수 없습니다.",
        ) from exc
    except gemini_service.GeminiUnavailableError as exc:
        raise AppError(
            status_code=502,
            code="GEMINI_UNAVAILABLE",
            message="추가 이미지 분석 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ) from exc

    waste_class = db.get(WasteClass, final_class_id)
    if waste_class is None:
        # Defensive: gemini_service already restricts to allowed_classes, so
        # this should be unreachable, but never trust a re-lookup blindly.
        raise AppError(
            status_code=502,
            code="GEMINI_BAD_RESPONSE",
            message="추가 이미지 분석 결과를 처리할 수 없습니다.",
        )

    feedback.final_class_id = final_class_id
    feedback.is_correct = False
    feedback.correction_source = "GEMINI"
    _commit(db)

    return NotInListResponse(
        feedback_id=feedback.feedback_id,
        final_class_id=final_class_id,
        major_category=waste_class.major_category,
        minor_category=waste_class.minor_category,
    )
