"""GET /api/v1/regions (섹션 7.2).

지역 Master 는 공개 데이터이고 로그인 전 지역 선택 UI 에서도 필요하므로,
이 엔드포인트만 인증 없이 호출할 수 있다.
(명세 7.2 의 "인증 필요 / 401 AUTH_REQUIRED" 에서 의도적으로 벗어난 부분.)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.database import get_db
from core.exceptions import database_error, validation_error
from models.region import Region
from schemas.region import RegionListResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/regions", tags=["regions"])

_ALLOWED_SIDO = {"서울특별시", "경기도"}
_UNSUPPORTED_SIDO_MESSAGE = "지원하지 않는 시·도입니다. 서울특별시 또는 경기도를 선택해주세요."


@router.get("", response_model=RegionListResponse)
def list_regions(
    sido_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RegionListResponse:
    if sido_name is not None and sido_name not in _ALLOWED_SIDO:
        # 섹션 7.2 는 이 엔드포인트의 422 message 를 카탈로그 기본 문구가 아닌
        # 아래 문구로 고정한다.
        raise validation_error(
            [{"field": "sido_name", "message": _UNSUPPORTED_SIDO_MESSAGE}],
            message=_UNSUPPORTED_SIDO_MESSAGE,
        )

    try:
        query = db.query(Region).order_by(Region.region_id)
        if sido_name is not None:
            query = query.filter(Region.sido_name == sido_name)
        regions = query.all()
    except SQLAlchemyError as exc:
        logger.exception("list regions DB error")
        raise database_error() from exc

    return RegionListResponse(items=regions)
