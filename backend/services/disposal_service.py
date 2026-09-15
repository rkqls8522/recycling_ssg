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

from core.exceptions import AppError
from models.region import Region
from models.waste_class import WasteClass
from services import public_waste_client

logger = logging.getLogger(__name__)


def _lookup(waste_class: WasteClass, region: Region) -> dict[str, str | None]:
    items = public_waste_client.fetch_items(sgg_name=region.sgg_name)
    best = public_waste_client.pick_best_item(
        items,
        major_category=waste_class.major_category,
        minor_category=waste_class.minor_category,
    )
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
