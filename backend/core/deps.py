"""Reusable FastAPI dependencies: DB session, current user, region guard."""

from __future__ import annotations

import logging

from fastapi import Depends, Header
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core import security
from core.database import get_db
from core.exceptions import (
    auth_required,
    auth_token_expired,
    auth_token_invalid,
    database_error,
    user_not_found,
)
from models.user import User

logger = logging.getLogger(__name__)


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.strip():
        raise auth_required()

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise auth_token_invalid()

    token = parts[1].strip()

    try:
        user_id = security.decode_access_token(token)
    except security.TokenExpiredError as exc:
        raise auth_token_expired() from exc
    except security.TokenInvalidError as exc:
        raise auth_token_invalid() from exc

    # 인증 API 의 오류 표에는 503 DATABASE_ERROR 가 포함되어 있으므로,
    # 사용자 조회 실패는 500 이 아니라 503 으로 보고한다.
    try:
        user = db.get(User, user_id)
    except SQLAlchemyError as exc:
        logger.exception("current user lookup DB error")
        raise database_error() from exc

    if user is None:
        raise user_not_found()

    return user
