"""테스트용 JWT 발급 스크립트.

회원가입/로그인 API를 거치지 않고, 특정 유저에 대한 JWT Access Token만
빠르게 발급받고 싶을 때 씁니다. `core/security.py`의 실제 발급 로직
(`create_access_token`)을 그대로 재사용하므로, 여기서 만든 토큰은
`Authorization: Bearer <token>` 헤더로 실제 API에 그대로 사용할 수 있습니다.

`--user-id` 든 `--email` 이든 **항상 DB를 실제로 조회**해서, 그 사용자가
정말 존재할 때만 토큰을 발급합니다(없으면 오류로 종료). 그래서 여기서 받은
토큰은 실제 서버의 `get_current_user()` 검증(= DB에 그 user_id가 있는지
확인)까지 통과하는 게 보장됩니다 — 존재하지 않는 유저의 토큰을 실수로
만드는 걸 막기 위함입니다.

사용법 (backend/ 폴더 안에서 실행):

    # 1) user_id 로 지정 — DB에서 조회해 실제로 존재할 때만 발급
    #    (없으면 오류)
    uv run python create_jwt_test.py --user-id 101

    # 2) email 로 지정해도 동일하게 동작 (DB에서 조회해 user_id 를 알아냄)
    uv run python create_jwt_test.py --email user@example.com

    # 3) 만료 시간을 직접 지정 (분 단위). 만료된 토큰을 일부러 만들 때 음수도 가능
    uv run python create_jwt_test.py --user-id 101 --minutes -1

curl 에 바로 넣을 수 있는 형태로 출력합니다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

import jwt

from core import security
from core.config import settings
from core.database import SessionLocal
from models.user import User


def _resolve_user_id(args: argparse.Namespace) -> int:
    """--user-id / --email 어느 쪽이든 DB에서 실제 사용자를 조회해 확인한다.

    존재하지 않으면 오류 메시지를 찍고 종료한다(SystemExit(1)) — 실제로
    없는 사용자의 토큰을 조용히 만들어주지 않기 위함이다.
    """
    db = SessionLocal()
    try:
        if args.user_id is not None:
            user = db.get(User, args.user_id)
            if user is None:
                print(f"오류: user_id={args.user_id} 인 사용자를 찾을 수 없습니다.", file=sys.stderr)
                raise SystemExit(1)
        else:
            user = db.query(User).filter(User.email == args.email).first()
            if user is None:
                print(f"오류: 이메일 '{args.email}' 을(를) 가진 사용자를 찾을 수 없습니다.", file=sys.stderr)
                raise SystemExit(1)

        print(f"DB에서 사용자를 찾았습니다: user_id={user.user_id}, email={user.email}")
        return user.user_id
    finally:
        db.close()


def create_token_for_user(user_id: int, minutes: int | None = None) -> str:
    """지정한 만료 시간(minutes)으로 access token 을 발급한다.

    minutes 를 안 주면 core/security.py 의 create_access_token 을 그대로
    호출한다(settings.jwt_access_token_expire_minutes 사용). minutes 를
    주면 그 값으로 잠깐 override 해서 발급한 뒤 원래 설정으로 되돌린다.
    """
    if minutes is None:
        return security.create_access_token(user_id)

    original = settings.jwt_access_token_expire_minutes
    try:
        settings.jwt_access_token_expire_minutes = minutes
        return security.create_access_token(user_id)
    finally:
        settings.jwt_access_token_expire_minutes = original


def main() -> None:
    parser = argparse.ArgumentParser(
        description="특정 유저에 대한 JWT Access Token을 발급하는 테스트 스크립트",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--user-id", type=int, help="토큰을 발급할 users.user_id (DB에서 존재 여부를 확인한 뒤 발급)")
    target.add_argument("--email", type=str, help="토큰을 발급할 사용자의 email (DB에서 조회해 user_id를 알아냄)")
    parser.add_argument(
        "--minutes",
        type=int,
        default=None,
        help="만료 시간(분). 생략하면 JWT_ACCESS_TOKEN_EXPIRE_MINUTES 설정값 사용. 음수를 주면 이미 만료된 토큰이 만들어짐",
    )
    args = parser.parse_args()

    user_id = _resolve_user_id(args)
    token = create_token_for_user(user_id, args.minutes)

    # 방금 만든 토큰이 서명/형식은 정상인지 확인 (안 되면 뭔가 잘못된 것).
    # verify_exp=False 로 디코딩해서, --minutes 로 일부러 만료시킨 토큰도
    # (ExpiredSignatureError 로 죽지 않고) 내용을 그대로 보여준다.
    decoded = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"verify_exp": False},
    )
    is_expired = decoded["exp"] < datetime.now(UTC).timestamp()

    print()
    print("=== JWT 발급 완료 ===")
    print(f"user_id     : {user_id}")
    print(f"algorithm   : {settings.jwt_algorithm}")
    print(f"issued_at   : {decoded['iat']}")
    print(f"expires_at  : {decoded['exp']}" + ("  (이미 만료됨)" if is_expired else ""))
    print()
    print("access_token:")
    print(token)
    print()
    print("Authorization 헤더:")
    print(f"Authorization: Bearer {token}")
    print()
    print("curl 예시:")
    print(f'curl -s http://127.0.0.1:8000/api/v1/users/me -H "Authorization: Bearer {token}"')


if __name__ == "__main__":
    main()
