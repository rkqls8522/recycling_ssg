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

# 실제 응답은 "품목명으로 찾는 여러 행"이 아니라 지역 하나당 한 행으로,
# 폐기물 종류별 컬럼 그룹(음식물/생활쓰레기/재활용/대형폐기물)이 나뉘어 있다
# (예: LF_WST_EMSN_DOW, RCYCL_EMSN_BGNG_TM, ...) -- 실제 발급받은 서비스키로
# 호출해 확인한 컬럼 구조 기준(2026-09-16). 우리 서비스는 17개 클래스 전부를
# 재활용품으로 취급하므로 대분류와 무관하게 항상 재활용(RCYCL) 그룹만 읽는다.
_GROUP_PREFIX = "RCYCL"


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


def pick_best_item(items: list[dict]) -> dict:
    """The API returns one row per region (sgg_name), not one row per waste
    item, so there is no item-name field to match against -- just take the
    (typically only) row for the requested region."""
    return items[0]


def _format_disposal_day(raw: str | None) -> str | None:
    """Raw values are "+"-joined day abbreviations (e.g. "월+화+수"); the
    spec's documented format is comma-separated (e.g. "화, 목")."""
    if not raw:
        return None
    return ", ".join(part for part in raw.split("+") if part)


def extract_disposal_fields(item: dict) -> dict[str, str | None]:
    def field(suffix: str) -> str | None:
        value = item.get(f"{_GROUP_PREFIX}_EMSN_{suffix}")
        return str(value).strip() if value not in (None, "") else None

    return {
        "disposal_day": _format_disposal_day(field("DOW")),
        "start_time": field("BGNG_TM"),
        "end_time": field("END_TM"),
        "disposal_method": field("MTHD"),
    }
