"""End-to-end Vision tests against the REAL YOLO checkpoint.

Skipped automatically when no checkpoint or no sample image is available
(e.g. on CI without the weights), so the suite stays runnable everywhere.
Set VISION_TEST_MODEL_PATH to point at a specific checkpoint.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = (
    REPO_ROOT / "ai" / "models" / "yolo" / "01_experiment_augmentation" / "report" / "final_best" / "prediction_samples"
)


def _find_checkpoint() -> Path | None:
    explicit = os.environ.get("VISION_TEST_MODEL_PATH")
    if explicit and Path(explicit).exists():
        return Path(explicit)

    for candidate in (REPO_ROOT / "weights" / "best.pt",):
        if candidate.exists():
            return candidate

    runs = REPO_ROOT / "ai" / "models" / "yolo" / "01_experiment_augmentation" / "runs"
    if runs.exists():
        found = sorted(runs.glob("*/weights/best.pt"))
        if found:
            return found[0]
    return None


CHECKPOINT = _find_checkpoint()
SAMPLE_IMAGES = sorted(SAMPLES_DIR.glob("*.jpg")) if SAMPLES_DIR.exists() else []

pytestmark = pytest.mark.skipif(
    CHECKPOINT is None or not SAMPLE_IMAGES,
    reason="no YOLO checkpoint or sample images available",
)


@pytest.fixture(scope="module")
def real_client():
    os.environ["MODEL_PATH"] = str(CHECKPOINT)
    os.environ["MODEL_VERSION"] = CHECKPOINT.parent.parent.name if CHECKPOINT else "unknown"

    from vision.core.config import get_settings

    get_settings.cache_clear()
    fresh = get_settings()

    from vision import inference
    from vision import main as vision_main
    from vision.core import config as vision_config

    vision_config.settings = fresh
    inference.settings = fresh
    vision_main.settings = fresh
    inference._model_singleton = None  # force a reload with the new path

    with TestClient(vision_main.app) as c:
        yield c


def test_real_model_loads_and_reports_healthy(real_client):
    resp = real_client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["model_loaded"] is True, "real checkpoint failed to load"
    assert body["model_version"]


def test_real_model_taxonomy_matches_shared_master_data(real_client):
    """The model's own class indices must line up with waste_classes.json —
    this is what makes class_id a shared contract (섹션 1, 4.3)."""
    from ultralytics import YOLO

    from vision.core.taxonomy import load_waste_classes

    resp = real_client.get("/internal/v1/classes")
    assert resp.status_code == 200
    served = {c["class_id"]: (c["major_category"], c["minor_category"]) for c in resp.json()["classes"]}

    taxonomy = load_waste_classes()
    assert served == taxonomy

    model_names = YOLO(str(CHECKPOINT)).names
    assert len(model_names) == len(taxonomy), "checkpoint class count != taxonomy size"
    for class_id, label in model_names.items():
        major, _minor = taxonomy[int(class_id)]
        # data.yaml uses "대분류/소분류"; allow the known 장남감/장난감 typo fix.
        assert label.split("/")[0] == major, f"class {class_id} major mismatch: {label} vs {major}"


def test_real_model_predicts_with_spec_shaped_response(real_client):
    image_path = SAMPLE_IMAGES[0]

    resp = real_client.post(
        "/internal/v1/predict",
        files={"image": (image_path.name, image_path.read_bytes(), "image/jpeg")},
    )

    # A real photo either yields a detection (200) or genuinely has no
    # central object (422) — both are valid spec outcomes.
    assert resp.status_code in (200, 422), resp.text
    body = resp.json()

    if resp.status_code == 422:
        assert body["code"] == "VISION_NO_MAIN_OBJECT"
        return

    assert body["major_category"] and body["minor_category"]
    scores = body["candidate_scores"]
    assert scores, "a successful prediction must carry at least one candidate"
    assert [s["score"] for s in scores] == sorted((s["score"] for s in scores), reverse=True)
    assert all(0.0 <= s["score"] <= 1.0 for s in scores)
    assert all("_" in s["category"] for s in scores)

    bbox = body["internal_meta"]["bbox"]
    assert all(0.0 <= bbox[k] <= 1.0 for k in ("x1", "y1", "x2", "y2"))
    assert bbox["x1"] < bbox["x2"] and bbox["y1"] < bbox["y2"]
    assert body["internal_meta"]["inference_ms"] > 0
