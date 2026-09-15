"""GET/POST /api/v1/favorites, DELETE /api/v1/favorites/{favorite_id} (섹션 12)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from core.exceptions import AppError, database_error
from models.favorite import Favorite
from models.user import User
from models.waste_class import WasteClass
from schemas.favorite import (
    FavoriteCreateRequest,
    FavoriteCreateResponse,
    FavoriteItemOut,
    FavoriteListResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/favorites", tags=["favorites"])


@router.get("", response_model=FavoriteListResponse)
def list_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FavoriteListResponse:
    try:
        rows = (
            db.query(Favorite, WasteClass)
            .join(WasteClass, Favorite.class_id == WasteClass.class_id)
            .filter(Favorite.user_id == current_user.user_id)
            .order_by(Favorite.created_at.desc())
            .all()
        )
    except SQLAlchemyError as exc:
        logger.exception("list favorites DB error")
        raise database_error() from exc

    items = [
        FavoriteItemOut(
            favorite_id=fav.favorite_id,
            class_id=wc.class_id,
            major_category=wc.major_category,
            minor_category=wc.minor_category,
            created_at=fav.created_at,
        )
        for fav, wc in rows
    ]
    return FavoriteListResponse(items=items)


@router.post("", response_model=FavoriteCreateResponse, status_code=status.HTTP_201_CREATED)
def create_favorite(
    payload: FavoriteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FavoriteCreateResponse:
    waste_class = db.get(WasteClass, payload.class_id)
    if waste_class is None:
        raise AppError(
            status_code=404,
            code="CLASS_NOT_FOUND",
            message="폐기물 분류 정보를 찾을 수 없습니다.",
        )

    favorite = Favorite(user_id=current_user.user_id, class_id=payload.class_id)
    db.add(favorite)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            status_code=409,
            code="FAVORITE_ALREADY_EXISTS",
            message="이미 즐겨찾기에 등록된 품목입니다.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("create favorite DB error")
        raise database_error() from exc

    db.refresh(favorite)
    return FavoriteCreateResponse(
        favorite_id=favorite.favorite_id,
        class_id=waste_class.class_id,
        major_category=waste_class.major_category,
        minor_category=waste_class.minor_category,
    )


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_favorite(
    favorite_id: int = Path(gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    favorite = db.get(Favorite, favorite_id)
    if favorite is None or favorite.user_id != current_user.user_id:
        raise AppError(
            status_code=404,
            code="FAVORITE_NOT_FOUND",
            message="즐겨찾기 정보를 찾을 수 없습니다.",
        )

    db.delete(favorite)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("delete favorite DB error")
        raise database_error() from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
