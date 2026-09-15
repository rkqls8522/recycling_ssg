"""Loads the shared regions.json / waste_classes.json taxonomy files that are
the single source of truth for Region and WasteClass Master data. The Vision
service loads the same waste_classes.json so YOLO class indices always line
up with ``waste_classes.class_id`` (spec 섹션 1, 4.2)."""

from __future__ import annotations

import json
from functools import lru_cache

from core.paths import taxonomy_data_dir


@lru_cache
def load_regions() -> list[dict]:
    path = taxonomy_data_dir() / "regions.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def load_waste_classes() -> dict[int, tuple[str, str]]:
    """Returns {class_id: (major_category, minor_category)}."""
    path = taxonomy_data_dir() / "waste_classes.json"
    with path.open("r", encoding="utf-8") as f:
        raw: dict[str, list[str]] = json.load(f)
    return {int(class_id): (major, minor) for class_id, (major, minor) in raw.items()}
