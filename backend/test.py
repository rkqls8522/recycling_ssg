"""공공데이터포털 생활폐기물 API 원본 응답 확인용 스크립트.

`services/public_waste_client.py` 는 응답을 파싱해 items 만 돌려주고 오류를
AppError 로 바꾸므로, **요청 URL / HTTP status / 원문 body** 를 그대로 보고
싶을 때 이 스크립트를 씁니다.

인증키와 base URL, timeout 은 모두 저장소 루트 `.env` 에서 읽습니다
(`PUBLIC_WASTE_API_SERVICE_KEY` / `PUBLIC_WASTE_API_BASE_URL` /
`PUBLIC_WASTE_API_TIMEOUT_SECONDS`). 키를 코드에 적지 마세요.

사용법 (backend/ 폴더 안에서 실행):

    uv run python test.py
    uv run python test.py 종로구
"""

from __future__ import annotations

import sys
from urllib.parse import unquote

import httpx

from core.config import settings

# .env 에는 공공데이터포털에서 복사한 URL-encoded 키가 들어 있습니다.
# httpx 가 전송 시 한 번 더 인코딩하므로, 여기서 원문으로 되돌려 이중
# 인코딩을 막습니다 (public_waste_client._service_key 와 같은 처리).
service_key = unquote((settings.public_waste_api_service_key or "").strip())

if not service_key:
    raise SystemExit(
        "PUBLIC_WASTE_API_SERVICE_KEY 가 비어 있습니다. "
        "저장소 루트 .env 를 확인하세요."
    )

sgg_name = sys.argv[1] if len(sys.argv) > 1 else "강남구"

params = {
    "serviceKey": service_key,
    "pageNo": 1,
    "numOfRows": 10,
    "returnType": "json",
    "cond[SGG_NM::LIKE]": sgg_name,
}

response = httpx.get(
    settings.public_waste_api_base_url,
    params=params,
    timeout=settings.public_waste_api_timeout_seconds,
)

print("요청 URL:")
# 인증키가 그대로 찍히지 않도록 가립니다.
print(str(response.url).replace(service_key, "<SERVICE_KEY>"))

print("\nHTTP STATUS:")
print(response.status_code)

print("\n응답:")
print(response.text)
