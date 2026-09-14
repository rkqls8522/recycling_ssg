"""행정안전부 생활쓰레기배출정보 API client (섹션 15.1).

공공데이터포털(data.go.kr) UDDI 표준데이터 조회 규격을 따르는 API로,
``cond[컬럼명::LIKE]=값`` 형태의 조건 파라미터와 ``response.header.resultCode``
기반 결과코드를 사용한다. 실제 배포 전 반드시 발급받은 서비스키로 한 번
호출해 응답 컬럼명을 확인하고, 아래 ``_FIELD_CANDIDATES`` 를 실제 컬럼명에
맞게 조정할 것.
"""

from __future__ import annotations

import logging
from urllib.parse import unquote

import httpx

from core.config import settings
from core.exceptions import AppError

logger = logging.getLogger(__name__)

# data.go.kr 결과코드 (response.header.resultCode) 매핑.
_RESULT_CODE_NORMAL = "00"
_RESULT_CODE_NO_DATA = {"03", "NODATA_ERROR"}
_RESULT_CODE_RATE_LIMIT = {"22", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"}
_RESULT_CODE_AUTH_ERROR = {
    "20", "21", "30", "31", "32", "33",
    "SERVICE_ACCESS_DENIED_ERROR",
    "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
    "UNREGISTERED_IP_ERROR",
}

# 응답 아이템의 실제 컬럼명이 배포 기관/버전에 따라 달라질 수 있어, 후보
# 목록 중 처음으로 매칭되는 키를 사용한다.
_FIELD_CANDIDATES: dict[str, list[str]] = {
    "sido": ["SIDO_NM", "sidoNm", "시도명"],
    "sgg": ["SGG_NM", "sggNm", "시군구명"],
    "item": ["ITEM_NM", "PBLIC_WSTE_NM", "itemNm", "품목명", "품목"],
    "day": ["EMISN_DOW_NM", "COLT_DOW_NM", "DSPOS_DOW_NM", "emisnDowNm", "배출요일", "수거요일"],
    "start_time": ["EMISN_BEGIN_TIME", "COLT_BEGIN_TIME", "emisnBeginTime", "배출시작시간"],
    "end_time": ["EMISN_END_TIME", "COLT_END_TIME", "emisnEndTime", "배출종료시간"],
    "method": ["EMISN_MTH_CN", "DSPOS_MTH_CN", "emisnMthCn", "배출방법", "비고"],
}


def _decoded_service_key() -> str:
    """공공데이터포털 서비스키는 발급 페이지에서 '인코딩' 형태(+, /, = 등이
    %XX 로 치환됨)로 복사되는 경우가 많다. httpx 는 params dict 값을
    전송 시 한 번 더 URL-encode 하므로, 이미 encode 된 키를 그대로 넘기면
    이중 인코딩되어 인증에 실패한다(흔한 실수). 따라서 저장값을 항상
    ``unquote`` 로 원문 상태로 되돌린 뒤 httpx가 인코딩을 한 번만
    수행하도록 한다. 원문 키에 우연히 '%'가 없다면 unquote는 아무 효과가
    없으므로 이미 원문인 키에도 안전하다."""
    raw = (settings.public_waste_api_service_key or "").strip()
    return unquote(raw)


def _client() -> httpx.Client:
    return httpx.Client(timeout=settings.public_waste_api_timeout_seconds)


def fetch_items(*, sgg_name: str) -> list[dict]:
    """지역(시군구) 기준으로 배출 정보 원본 items 목록을 조회한다.

    데이터가 없으면 PUBLIC_WASTE_NOT_FOUND, 인증/한도/네트워크 오류는 각각
    대응하는 AppError 를 발생시킨다.
    """
    service_key = _decoded_service_key()
    if not service_key:
        raise AppError(
            status_code=502,
            code="PUBLIC_WASTE_UNAVAILABLE",
            message="분리배출 정보 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
        )

    params = {
        "serviceKey": service_key,
        "type": "json",
        "pageNo": 1,
        "numOfRows": 100,
        "cond[SGG_NM::LIKE]": sgg_name,
    }

    try:
        with _client() as client:
            response = client.get(settings.public_waste_api_base_url, params=params)
    except httpx.TimeoutException as exc:
        raise AppError(
            status_code=504,
            code="PUBLIC_WASTE_TIMEOUT",
            message="분리배출 정보 조회 시간이 초과되었습니다. 다시 시도해주세요.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("공공데이터 API 연결 실패")
        raise AppError(
            status_code=502,
            code="PUBLIC_WASTE_UNAVAILABLE",
            message="분리배출 정보 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ) from exc

    if response.status_code == 401 or response.status_code == 403:
        raise AppError(
            status_code=502,
            code="PUBLIC_WASTE_AUTH_ERROR",
            message="분리배출 정보 서비스 인증에 실패했습니다.",
        )
    if response.status_code == 429:
        raise AppError(
            status_code=503,
            code="PUBLIC_WASTE_RATE_LIMITED",
            message="분리배출 정보 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
        )
    if response.status_code != 200:
        raise AppError(
            status_code=502,
            code="PUBLIC_WASTE_UNAVAILABLE",
            message="분리배출 정보 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise AppError(
            status_code=502,
            code="PUBLIC_WASTE_UNAVAILABLE",
            message="분리배출 정보 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ) from exc

    body = (payload.get("response") or payload).get("body", {}) if isinstance(payload, dict) else {}
    header = (payload.get("response") or payload).get("header", {}) if isinstance(payload, dict) else {}
    result_code = str(header.get("resultCode", _RESULT_CODE_NORMAL))

    if result_code in _RESULT_CODE_AUTH_ERROR:
        raise AppError(
            status_code=502,
            code="PUBLIC_WASTE_AUTH_ERROR",
            message="분리배출 정보 서비스 인증에 실패했습니다.",
        )
    if result_code in _RESULT_CODE_RATE_LIMIT:
        raise AppError(
            status_code=503,
            code="PUBLIC_WASTE_RATE_LIMITED",
            message="분리배출 정보 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
        )

    items = body.get("items", [])
    if isinstance(items, dict):
        # 일부 UDDI 응답은 items가 단일 객체이거나 {"item": [...]} 형태다.
        items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]

    if not items or result_code in _RESULT_CODE_NO_DATA:
        raise AppError(
            status_code=404,
            code="PUBLIC_WASTE_NOT_FOUND",
            message="해당 지역의 분리배출 정보를 찾을 수 없습니다.",
        )

    return items


def _get_field(item: dict, field: str) -> str | None:
    for key in _FIELD_CANDIDATES[field]:
        if key in item and item[key] not in (None, ""):
            return str(item[key]).strip()
    return None


def pick_best_item(items: list[dict], *, major_category: str, minor_category: str) -> dict:
    """품목명이 있는 필드를 대/소분류 문자열과 비교해 가장 근접한 행을 고른다.
    소분류 일치를 최우선으로, 그다음 대분류 일치를 시도하고, 매칭되는 것이
    없으면 첫 번째 행을 사용한다."""
    if minor_category:
        for item in items:
            if minor_category in (_get_field(item, "item") or ""):
                return item
    if major_category:
        for item in items:
            if major_category in (_get_field(item, "item") or ""):
                return item
    return items[0]


def extract_disposal_fields(item: dict) -> dict[str, str | None]:
    return {
        "disposal_day": _get_field(item, "day"),
        "start_time": _get_field(item, "start_time"),
        "end_time": _get_field(item, "end_time"),
        "disposal_method": _get_field(item, "method"),
    }
