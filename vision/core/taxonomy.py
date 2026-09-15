"""Loads the same data/taxonomy/waste_classes.json the Backend seeds its
``waste_classes`` table from, so a YOLO class index always maps to the same
(major, minor) category on both sides (spec 섹션 1, 4.2)."""

from __future__ import annotations

import json
from functools import lru_cache

from vision.core.config import settings


@lru_cache
def load_waste_classes() -> dict[int, tuple[str, str]]:
    path = settings.resolved_taxonomy_dir / "waste_classes.json"
    with path.open("r", encoding="utf-8") as f:
        raw: dict[str, list[str]] = json.load(f)
    return {int(class_id): (major, minor) for class_id, (major, minor) in raw.items()}


def category_label(class_id: int) -> tuple[str, str]:
    """Returns (major_category, minor_category) for a class_id, falling back
    to a generic placeholder if the model somehow emits an index outside the
    known taxonomy (should not happen with a correctly trained checkpoint)."""
    classes = load_waste_classes()
    if class_id in classes:
        return classes[class_id]
    return ("미분류", f"class_{class_id}")
