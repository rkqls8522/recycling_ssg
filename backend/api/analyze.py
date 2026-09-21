"""POST /api/v1/analyze (섹션 8.1, 19).

Flow: JWT -> region check -> image validation -> Vision predict ->
main-object gate -> S3 upload -> DB transaction
(images/feedback/feedback_candidates) -> confidence gate -> (SUCCESS 경로만)
best-effort disposal lookup -> SUCCESS/RETAKE_REQUIRED response.

- AI_NO_MAIN_OBJECT(메인 객체 자체를 못 찾음): 저장할 예측값이 없으므로
  S3/DB 어디에도 저장하지 않는다.
- AI_LOW_CONFIDENCE(신뢰도 < threshold): 예측 자체는 있으므로 SUCCESS와
  동일하게 S3/DB에 저장하되(재학습 데이터 수집 목적), 사용자에게는 그대로
  RETAKE_REQUIRED로 응답한다. 이렇게 저장된 행은 final_class_id/is_correct/
  correction_source가 전부 NULL(미응답)로 남고, predicted_score < threshold로
  나중에 구분해서 조회할 수 있다.
- 어느 쪽이든 DB 트랜잭션 실패 시 업로드된 S3 객체를 보상 삭제한다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user
from core.exceptions import database_error, user_region_required
from models.feedback import Feedback
from models.feedback_candidate import FeedbackCandidate
from models.image import Image
from models.user import User
from models.waste_class import WasteClass
from schemas.analyze import AnalyzeRetakeResponse, AnalyzeSuccessResponse
from schemas.common import RegionOut
from services import image_processing, storage, vision_client
from services.disposal_service import get_disposal_info_or_warn, get_rule_info_or_warn
from services.image_validation import validate_and_read

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["analyze"])


@router.post("/analyze", response_model=None)
def analyze_image(
    request: Request,
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalyzeSuccessResponse | AnalyzeRetakeResponse:
    request_id = request.state.request_id

    if current_user.region_id is None:
        raise user_region_required("분석 전에 거주 지역을 선택해주세요.")
    region = current_user.region

    # 1) Validate the raw upload as the client sent it (type/size/empty).
    raw_bytes, _upload_content_type = validate_and_read(image)
    # 2) Decode + EXIF-correct + downscale (<=1920px, 비율 유지) + re-encode.
    #    The Vision Server and S3 both receive these SAME processed bytes,
    #    so the stored image is exactly what Vision analyzed.
    file_bytes, content_type, extension = image_processing.process_upload(raw_bytes)

    try:
        prediction = vision_client.predict(
            image_bytes=file_bytes,
            filename=f"upload.{extension}",
            content_type=content_type,
            request_id=request_id,
        )
    except vision_client.VisionNoMainObjectError:
        return AnalyzeRetakeResponse(
            code="AI_NO_MAIN_OBJECT",
            message="분류할 물체를 화면 중앙에 위치시킨 뒤 다시 촬영해주세요.",
            # threshold는 고정 설정값이라 항상 내려줄 수 있다. score는 정말로
            # 낼 수 없다 -- Vision이 low_confidence_floor(0.05)조차 넘는 탐지를
            # 하나도 못 했으므로 점수를 매길 대상 자체가 없다.
            threshold=settings.vision_confidence_threshold,
            request_id=request_id,
        )

    # candidate_scores는 Top-1(prediction.class_id/score)을 제외한 "다른 후보"만
    # 담고 있다 -- Vision이 이미 score 내림차순으로 정렬해서 내려준다.
    other_candidates = prediction.candidate_scores
    is_low_confidence = prediction.score < settings.vision_confidence_threshold

    s3_key = storage.upload_image(
        file_bytes=file_bytes,
        content_type=content_type,
        user_id=current_user.user_id,
        extension=extension,
    )

    try:
        image_row = Image(s3_key=s3_key, content_type=content_type)
        db.add(image_row)
        db.flush()

        bbox = prediction.internal_meta.bbox
        feedback_row = Feedback(
            user_id=current_user.user_id,
            image_id=image_row.image_id,
            predicted_class_id=prediction.class_id,
            predicted_score=prediction.score,
            bbox_x1=bbox.x1,
            bbox_y1=bbox.y1,
            bbox_x2=bbox.x2,
            bbox_y2=bbox.y2,
            model_version=prediction.internal_meta.model_version,
        )
        db.add(feedback_row)
        db.flush()

        for rank, candidate in enumerate(other_candidates, start=1):
            db.add(
                FeedbackCandidate(
                    feedback_id=feedback_row.feedback_id,
                    class_id=candidate.class_id,
                    score=candidate.score,
                    rank=rank,
                )
            )

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("analyze DB transaction failed, compensating S3 delete key=%s", s3_key)
        storage.delete_object(s3_key)
        raise database_error() from exc

    if is_low_confidence:
        return AnalyzeRetakeResponse(
            code="AI_LOW_CONFIDENCE",
            message="분석 신뢰도가 낮습니다. 물체를 중앙에 선명하게 두고 다시 촬영해주세요.",
            threshold=settings.vision_confidence_threshold,
            score=prediction.score,
            feedback_id=feedback_row.feedback_id,
            request_id=request_id,
        )

    # Best-effort disposal-day lookup: never fails the request (섹션 15.1).
    waste_class = db.get(WasteClass, prediction.class_id)
    disposal_day, warnings = get_disposal_info_or_warn(waste_class, region) if waste_class else (None, [])

    # Best-effort disposal-method lookup via RAG 서비스 (node2).
    region_out = RegionOut.model_validate(region)
    classification_payload = {
        "status": "SUCCESS",
        "major_category": prediction.major_category,
        "minor_category": prediction.minor_category,
        "class_id": prediction.class_id,
        "score": prediction.score,
        "candidate_scores": [
            {"class_id": c.class_id, "category": "", "score": c.score} for c in other_candidates
        ],
        "user_region": region_out.model_dump(),
        "disposal_day": disposal_day,
        "image_id": image_row.image_id,
        "feedback_id": feedback_row.feedback_id,
        "warnings": warnings,
    }
    national_rule, region_rule, rule_warnings = get_rule_info_or_warn(classification_payload)
    warnings = warnings + rule_warnings

    return AnalyzeSuccessResponse(
        major_category=prediction.major_category,
        minor_category=prediction.minor_category,
        class_id=prediction.class_id,
        score=prediction.score,
        candidate_scores=other_candidates,
        user_region=region_out,
        disposal_day=disposal_day,
        national_rule=national_rule,
        region_rule=region_rule,
        image_id=image_row.image_id,
        feedback_id=feedback_row.feedback_id,
        warnings=warnings,
    )
