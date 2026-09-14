"""GET /api/v1/users/me, PATCH /api/v1/users/me/region (섹션 7.1, 7.3)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from core.exceptions import AppError, database_error
from models.region import Region
from models.user import User
from schemas.user import RegionUpdateRequest, RegionUpdateResponse, UserProfileOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserProfileOut)
def get_my_profile(current_user: User = Depends(get_current_user)) -> UserProfileOut:
    return UserProfileOut.model_validate(current_user)


@router.patch("/me/region", response_model=RegionUpdateResponse)
def update_my_region(
    payload: RegionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RegionUpdateResponse:
    try:
        region = db.get(Region, payload.region_id)
    except SQLAlchemyError as exc:
        logger.exception("region lookup DB error")
        raise database_error() from exc

    if region is None:
        raise AppError(
            status_code=404,
            code="REGION_NOT_FOUND",
            message="지원하지 않는 지역입니다.",
        )

    current_user.region_id = region.region_id
    try:
        db.commit()
        db.refresh(current_user)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("update region DB error")
        raise database_error() from exc

    return RegionUpdateResponse(user_id=current_user.user_id, region=region)
