"""GET /api/v1/disposal/schedule (섹션 10.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from core.exceptions import AppError, user_region_required
from models.user import User
from models.waste_class import WasteClass
from schemas.disposal import DisposalScheduleResponse
from services.disposal_service import get_disposal_info_or_raise

router = APIRouter(prefix="/api/v1/disposal", tags=["disposal"])


@router.get("/schedule", response_model=DisposalScheduleResponse)
def get_disposal_schedule(
    class_id: int = Query(gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DisposalScheduleResponse:
    waste_class = db.get(WasteClass, class_id)
    if waste_class is None:
        raise AppError(
            status_code=404,
            code="CLASS_NOT_FOUND",
            message="폐기물 분류 정보를 찾을 수 없습니다.",
        )

    if current_user.region_id is None:
        raise user_region_required()
    region = current_user.region

    fields = get_disposal_info_or_raise(waste_class, region)

    return DisposalScheduleResponse(
        class_id=waste_class.class_id,
        major_category=waste_class.major_category,
        minor_category=waste_class.minor_category,
        region=region,
        disposal_day=fields.get("disposal_day"),
        start_time=fields.get("start_time"),
        end_time=fields.get("end_time"),
        disposal_method=fields.get("disposal_method"),
    )
