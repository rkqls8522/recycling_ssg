"""POST /api/v1/analyze (섹션 8.1, 19).

Flow: JWT -> region check -> image validation -> Vision predict ->
confidence/main-object gate -> S3 upload -> DB transaction
(images/feedback/feedback_candidates) -> best-effort disposal lookup ->
SUCCESS response. Any failure before the DB commit leaves no S3/DB trace;
any failure *during* the DB transaction triggers a compensating S3 delete.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user
from core.exceptions import AppError, database_error, user_region_required
from models.feedback import Feedback
from models.feedback_candidate import FeedbackCandidate
from models.image import Image
from models.user import User
from models.waste_class import WasteClass
from schemas.analyze import AnalyzeRetakeResponse, AnalyzeSuccessResponse
from schemas.common import RegionOut
from services import s3_service, vision_client
from services.disposal_service import get_disposal_info_or_warn
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

    file_bytes, content_type, extension = validate_and_read(image)

    try:
        prediction = vision_client.predict(
            image_bytes=file_bytes,
            filename=image.filename or f"upload.{extension}",
            content_type=content_type,
            request_id=request_id,
        )
    except vision_client.VisionNoMainObjectError:
        return AnalyzeRetakeResponse(
            code="AI_NO_MAIN_OBJECT",
            message="분류할 물체를 화면 중앙에 위치시킨 뒤 다시 촬영해주세요.",
            threshold=None,
            request_id=request_id,
        )

    candidates = sorted(prediction.candidate_scores, key=lambda c: c.score, reverse=True)
    if not candidates:
        raise AppError(
            status_code=502,
            code="VISION_BAD_RESPONSE",
            message="이미지 분석 결과를 처리할 수 없습니다.",
        )

    top1 = candidates[0]
    if top1.score < settings.vision_confidence_threshold:
        return AnalyzeRetakeResponse(
            code="AI_LOW_CONFIDENCE",
            message="분석 신뢰도가 낮습니다. 물체를 중앙에 선명하게 두고 다시 촬영해주세요.",
            threshold=settings.vision_confidence_threshold,
            request_id=request_id,
        )

    s3_key = s3_service.upload_image(
        file_bytes=file_bytes,
        content_type=content_type,
        user_id=current_user.user_id,
        extension=extension,
    )

    try:
        image_row = Image(user_id=current_user.user_id, s3_key=s3_key)
        db.add(image_row)
        db.flush()

        bbox = prediction.internal_meta.bbox
        feedback_row = Feedback(
            user_id=current_user.user_id,
            image_id=image_row.image_id,
            predicted_class_id=top1.class_id,
            predicted_score=top1.score,
            bbox_x1=bbox.x1,
            bbox_y1=bbox.y1,
            bbox_x2=bbox.x2,
            bbox_y2=bbox.y2,
            model_version=prediction.internal_meta.model_version,
        )
        db.add(feedback_row)
        db.flush()

        for rank, candidate in enumerate(candidates, start=1):
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
        s3_service.delete_object(s3_key)
        raise database_error() from exc

    # Best-effort disposal-day lookup: never fails the request (섹션 15.1).
    waste_class = db.get(WasteClass, top1.class_id)
    disposal_day, warnings = get_disposal_info_or_warn(waste_class, region) if waste_class else (None, [])

    return AnalyzeSuccessResponse(
        major_category=prediction.major_category,
        minor_category=prediction.minor_category,
        candidate_scores=candidates,
        user_region=RegionOut.model_validate(region),
        disposal_day=disposal_day,
        image_id=image_row.image_id,
        feedback_id=feedback_row.feedback_id,
        warnings=warnings,
    )
