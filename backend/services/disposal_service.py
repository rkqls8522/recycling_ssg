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
    # 86개 클래스 전부를 재활용품으로 취급하므로 waste_class 자체는 조회에
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
