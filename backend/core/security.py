"""Password hashing (bcrypt) and JWT access token issuing/verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from core.config import settings

_BCRYPT_MAX_BYTES = 72  # bcrypt silently truncates beyond this; we reject instead.


def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class TokenExpiredError(Exception):
    pass


class TokenInvalidError(Exception):
    pass


def decode_access_token(token: str) -> int:
    """Returns the user_id encoded in the token, or raises Token*Error."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError from exc

    sub = payload.get("sub")
    if sub is None:
        raise TokenInvalidError
    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise TokenInvalidError from exc
