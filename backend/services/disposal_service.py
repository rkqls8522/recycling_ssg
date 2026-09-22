"""Combines a WasteClass + Region into a disposal-schedule lookup against
the 행정안전부 API. Two entry points are exposed because the spec treats
failures differently depending on the caller:

* ``get_disposal_info_or_raise`` -- used by GET /api/v1/disposal/schedule,
  a direct lookup endpoint, so external failures propagate as HTTP errors.
* ``get_disposal_info_or_warn`` -- used by POST /api/v1/analyze, where the
  analysis itself must still succeed even if the external API is down; the
  failure is reported via the ``warnings`` array instead (섹션 15.1).
"""

from __future__ import annotations

import logging
import os

import requests

from core.exceptions import AppError
from models.region import Region
from models.waste_class import WasteClass
from services import public_waste_client

logger = logging.getLogger(__name__)


def _lookup(waste_class: WasteClass, region: Region) -> dict[str, str | None]:
    # 17개 클래스 전부를 재활용품으로 취급하므로 waste_class 자체는 조회에
    # 쓰이지 않는다 -- 시그니처에는 남겨서 호출부(analyze/disposal API)가
    # "이 폐기물 종류 + 이 지역" 조합이라는 의도를 그대로 드러내게 한다.
    items = public_waste_client.fetch_items(sgg_name=region.sgg_name)
    best = public_waste_client.pick_best_item(items)
    return public_waste_client.extract_disposal_fields(best)


def get_disposal_info_or_raise(waste_class: WasteClass, region: Region) -> dict[str, str | None]:
    return _lookup(waste_class, region)


def get_disposal_info_or_warn(
    waste_class: WasteClass, region: Region
) -> tuple[str | None, list[str]]:
    """Returns (disposal_day, warnings). Never raises."""
    try:
        fields = _lookup(waste_class, region)
        return fields.get("disposal_day"), []
    except AppError as exc:
        logger.warning(
            "disposal info lookup failed during analyze, degrading gracefully: %s", exc.code
        )
        return None, [exc.code]
    except Exception:
        logger.exception("unexpected disposal info lookup failure during analyze")
        return None, ["PUBLIC_WASTE_UNAVAILABLE"]



RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8001/rule_node")


def get_rule_info_or_warn(
    classification_payload: dict,
) -> tuple[dict | None, dict | None, list[str]]:
    """RAG 서비스(node2)에 배출방법(national_rule/region_rule)을 조회.

    Returns (national_rule, region_rule, warnings). Never raises —
    disposal_day 조회와 동일하게 best-effort로 동작 (섹션 15.1 패턴).
    """
    try:
        response = requests.post(RAG_SERVICE_URL, json=classification_payload, timeout=5)
        response.raise_for_status()
        disposal_result = response.json().get("disposal_result", {})
        return disposal_result.get("national_rule"), disposal_result.get("region_rule"), []
    except requests.RequestException:
        logger.warning("rule info (RAG service) lookup failed during analyze, degrading gracefully")
        return None, None, ["RAG_SERVICE_UNAVAILABLE"]
    except Exception:
        logger.exception("unexpected rule info lookup failure during analyze")
        return None, None, ["RAG_SERVICE_UNAVAILABLE"]


RAG_RECLASSIFY_URL = os.getenv("RAG_RECLASSIFY_URL", "http://localhost:8001/reclassify")

RAG_CHAT_URL = os.getenv("RAG_CHAT_URL", "http://localhost:8001/chat_node")


def get_chat_answer_or_warn(
    *, message: str, major_category: str, minor_category: str, user_region: dict
) -> tuple[str | None, list[str]]:
    """RAG 서비스의 챗봇 노드(node4)에 후속 질문 답변을 요청.

    Returns (answer, warnings). Never raises -- get_rule_info_or_warn과 동일한
    best-effort 패턴. 챗봇은 (구) Gemini 미설정 시에도 결정적 답변으로 계속
    동작하는 게 기존 설계라서, RAG 서비스가 죽어있는 경우도 똑같이 취급해
    호출부(agent/service.py)가 폴백 답변으로 대체하게 한다.
    """
    try:
        response = requests.post(
            RAG_CHAT_URL,
            json={
                "message": message,
                "major_category": major_category,
                "minor_category": minor_category,
                "user_region": user_region,
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("answer"), []
    except requests.RequestException:
        logger.warning("chat (RAG service) lookup failed, degrading to fallback answer")
        return None, ["RAG_SERVICE_UNAVAILABLE"]
    except Exception:
        logger.exception("unexpected chat (RAG service) failure")
        return None, ["RAG_SERVICE_UNAVAILABLE"]


def reclassify_or_raise(img_url: str, user_region: dict) -> dict:
    """RAG 서비스의 재분류 그래프(classify -> judge -> disposal_lookup)를 호출.

    POST /api/v1/feedback/{feedback_id}/not-in-list 자체의 핵심 로직이므로
    (disposal_day/rule 조회처럼 곁다리 정보가 아님) 실패를 warnings 로 감추지
    않고 AppError 로 전파해 호출부가 사용자에게 실패를 알리게 한다. LLM
    재분류 + judge 검증 루프를 거치므로 rule_node 조회보다 넉넉한 timeout을 둔다.
    """
    try:
        response = requests.post(
            RAG_RECLASSIFY_URL,
            json={"img_url": img_url, "user_region": user_region},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        logger.warning("RAG reclassify timed out")
        raise AppError(
            status_code=504,
            code="RAG_RECLASSIFY_TIMEOUT",
            message="추가 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요.",
        ) from exc
    except requests.RequestException as exc:
        logger.warning("RAG reclassify service unavailable: %s", exc)
        raise AppError(
            status_code=502,
            code="RAG_SERVICE_UNAVAILABLE",
            message="추가 이미지 분석 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ) from exc
    except Exception as exc:
        logger.exception("unexpected RAG reclassify failure")
        raise AppError(
            status_code=502,
            code="RAG_BAD_RESPONSE",
            message="추가 이미지 분석 결과를 처리할 수 없습니다.",
        ) from exc
