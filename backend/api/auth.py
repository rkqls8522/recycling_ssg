"""POST /api/v1/auth/signup, /login, /logout (섹션 6)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from core import security
from core.database import get_db
from core.deps import get_current_user
from core.exceptions import AppError, database_error
from models.user import User
from schemas.auth import LoginRequest, LoginResponse, SignupRequest, SignupResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    try:
        existing = db.query(User).filter(User.email == payload.email).first()
    except SQLAlchemyError as exc:
        logger.exception("signup duplicate-check DB error")
        raise database_error() from exc

    if existing is not None:
        raise AppError(
            status_code=409,
            code="AUTH_EMAIL_EXISTS",
            message="이미 가입된 이메일입니다.",
        )

    user = User(
        email=payload.email,
        password_hash=security.hash_password(payload.password),
        region_id=None,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            status_code=409,
            code="AUTH_EMAIL_EXISTS",
            message="이미 가입된 이메일입니다.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("signup DB error")
        raise database_error() from exc

    return SignupResponse(
        user_id=user.user_id,
        email=user.email,
        region=None,
        created_at=user.created_at,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        user = db.query(User).filter(User.email == payload.email).first()
    except SQLAlchemyError as exc:
        logger.exception("login DB error")
        raise database_error() from exc

    if user is None or not security.verify_password(payload.password, user.password_hash):
        raise AppError(
            status_code=401,
            code="AUTH_INVALID_CREDENTIALS",
            message="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    token = security.create_access_token(user.user_id)
    return LoginResponse(access_token=token, token_type="bearer", user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: User = Depends(get_current_user)) -> Response:
    # Stateless JWT: nothing to invalidate server-side. Token validity was
    # already verified by get_current_user; the client discards the token.
    return Response(status_code=status.HTTP_204_NO_CONTENT)
