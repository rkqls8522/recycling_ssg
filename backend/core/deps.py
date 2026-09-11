"""Reusable FastAPI dependencies: DB session, current user, region guard."""

from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from core import security
from core.database import get_db
from core.exceptions import (
    auth_required,
    auth_token_expired,
    auth_token_invalid,
    user_not_found,
)
from models.user import User


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

    user = db.get(User, user_id)
    if user is None:
        raise user_not_found()

    return user
