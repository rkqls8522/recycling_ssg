"""POST /api/v1/feedback/{feedback_id}/confirm, /select-candidate,
/not-in-list (섹션 9)."""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, Path
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from core.exceptions import AppError, database_error, user_region_required
from models.feedback import Feedback
from models.feedback_candidate import FeedbackCandidate
from models.image import Image
from models.user import User
from models.waste_class import WasteClass
from schemas.analyze import NationalRuleOut, RegionRuleOut
from schemas.feedback import (
    ConfirmResponse,
    NotInListResponse,
    NotInListRetakeResponse,
    SelectCandidateRequest,
    SelectCandidateResponse,
)
from services import disposal_service, storage
from services.disposal_service import get_disposal_info_or_warn

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


@router.post("/{feedback_id}/not-in-list", response_model=None)
def not_in_list(
    feedback_id: int = Path(gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotInListResponse | NotInListRetakeResponse:
    """"여기없음" 선택 시 RAG 서비스의 재분류 그래프(classify -> judge 루프
    -> disposal_lookup)를 호출해 최종 class_id 와 배출 규정을 함께 반환한다.
    (구 Gemini 단독 재분류 방식을 대체 -- 섹션 9.3)"""
    feedback = _load_owned_feedback(db, feedback_id, current_user)

    image = db.get(Image, feedback.image_id)
    if image is None:
        raise AppError(
            status_code=404,
            code="FEEDBACK_NOT_FOUND",
            message="피드백 정보를 찾을 수 없습니다.",
        )

    if current_user.region_id is None:
        raise user_region_required()
    region = current_user.region

    image_bytes = storage.download_image(image.s3_key)
    img_url = f"data:{image.content_type};base64,{base64.b64encode(image_bytes).decode()}"
    user_region = {
        "region_id": region.region_id,
        "sido_name": region.sido_name,
        "sgg_name": region.sgg_name,
    }

    result = disposal_service.reclassify_or_raise(img_url=img_url, user_region=user_region)

    major_category = result.get("major_category")
    minor_category = result.get("minor_category")
    if result.get("needs_retake") or not major_category or not minor_category:
        return NotInListRetakeResponse()

    waste_class = (
        db.query(WasteClass)
        .filter(
            WasteClass.major_category == major_category,
            WasteClass.minor_category == minor_category,
        )
        .first()
    )
    if waste_class is None:
        raise AppError(
            status_code=502,
            code="RAG_BAD_RESPONSE",
            message="추가 이미지 분석 결과를 처리할 수 없습니다.",
        )

    feedback.final_class_id = waste_class.class_id
    feedback.is_correct = False
    feedback.correction_source = "GEMINI"
    _commit(db)

    disposal_day, _warnings = get_disposal_info_or_warn(waste_class, region)

    disposal_result = result.get("disposal_result") or {}
    national_rule = disposal_result.get("national_rule")
    region_rule = disposal_result.get("region_rule")

    return NotInListResponse(
        feedback_id=feedback.feedback_id,
        final_class_id=waste_class.class_id,
        major_category=waste_class.major_category,
        minor_category=waste_class.minor_category,
        disposal_day=disposal_day,
        national_rule=NationalRuleOut(**national_rule) if national_rule else None,
        region_rule=RegionRuleOut(**region_rule) if region_rule else None,
    )
