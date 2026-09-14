"""Vision Server API contract tests (섹션 13.1, 13.2, 14.3).

The YOLO checkpoint is replaced by a stub model so every documented
response shape and error mapping is asserted without torch/CUDA. A second
module (test_api_real_model.py) exercises the real checkpoint when one is
available.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vision import inference
from vision import main as vision_main
from vision.core.config import settings
from vision.inference import ImageDecodeError, ModelNotReadyError, NoMainObjectError

JPEG = ("photo.jpg", b"\xff\xd8\xff\xe0stub-jpeg", "image/jpeg")


class _StubBox:
    x1, y1, x2, y2 = 0.25, 0.18, 0.76, 0.88


class _StubModel:
    """Mimics VisionModel's public surface (is_ready + predict)."""

    def __init__(self, *, ready: bool = True, raises: type[Exception] | None = None) -> None:
        self.is_ready = ready
        self._raises = raises

    def predict(self, file_bytes: bytes):
        if self._raises is not None:
            raise self._raises
        candidates = [
            {"class_id": 77, "category": "플라스틱류_욕실용품", "score": 0.8123},
            {"class_id": 76, "category": "플라스틱류_바구니", "score": 0.1211},
            {"class_id": 74, "category": "플라스틱류_대용량플라스틱통", "score": 0.0432},
        ]
        return candidates, 31.7, _StubBox()


@pytest.fixture
def client():
    with TestClient(vision_main.app) as c:
        yield c


@pytest.fixture
def stub_model(monkeypatch):
    def _install(**kwargs):
        model = _StubModel(**kwargs)
        monkeypatch.setattr(inference, "get_model", lambda: model)
        monkeypatch.setattr(vision_main, "get_model", lambda: model)
        return model

    return _install


# --- POST /internal/v1/predict --------------------------------------------


def test_predict_returns_full_internal_contract(client, stub_model):
    stub_model()

    resp = client.post("/internal/v1/predict", files={"image": JPEG})

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body) == {"major_category", "minor_category", "candidate_scores", "internal_meta"}
    assert body["major_category"] == "플라스틱류"
    assert body["minor_category"] == "욕실용품"

    scores = body["candidate_scores"]
    assert len(scores) == 3
    assert all(set(s) == {"class_id", "category", "score"} for s in scores)
    # Top-K ordered by score desc (SR-07).
    assert [s["score"] for s in scores] == sorted((s["score"] for s in scores), reverse=True)
    assert scores[0]["category"] == "플라스틱류_욕실용품"  # 대분류_소분류 형식

    meta = body["internal_meta"]
    assert set(meta) == {"bbox", "model_version", "inference_ms"}
    bbox = meta["bbox"]
    assert set(bbox) == {"x1", "y1", "x2", "y2"}
    # 0~1 normalized XYXY with x1<x2, y1<y2 (섹션 3.3).
    assert all(0.0 <= bbox[k] <= 1.0 for k in ("x1", "y1", "x2", "y2"))
    assert bbox["x1"] < bbox["x2"] and bbox["y1"] < bbox["y2"]
    assert isinstance(meta["model_version"], str) and meta["model_version"]
    assert isinstance(meta["inference_ms"], (int, float))


def test_predict_echoes_request_id_from_backend(client, stub_model):
    stub_model()
    supplied = "550e8400-e29b-41d4-a716-446655440000"

    resp = client.post(
        "/internal/v1/predict", files={"image": JPEG}, headers={"X-Request-ID": supplied}
    )

    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == supplied


def test_predict_no_main_object_is_422_for_backend_conversion(client, stub_model):
    """Backend converts this into HTTP 200 RETAKE_REQUIRED (섹션 13.1)."""
    stub_model(raises=NoMainObjectError)

    resp = client.post("/internal/v1/predict", files={"image": JPEG})

    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VISION_NO_MAIN_OBJECT"
    assert body["message"] == "화면 중앙에서 메인 객체를 찾지 못했습니다."
    assert set(body) == {"success", "code", "message", "details", "request_id"}
    assert body["success"] is False


def test_predict_decode_failure_is_400(client, stub_model):
    stub_model(raises=ImageDecodeError)

    resp = client.post("/internal/v1/predict", files={"image": JPEG})

    assert resp.status_code == 400
    assert resp.json()["code"] == "IMAGE_DECODE_FAILED"


def test_predict_model_not_ready_is_503(client, stub_model):
    stub_model(ready=False, raises=ModelNotReadyError)

    resp = client.post("/internal/v1/predict", files={"image": JPEG})

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "VISION_MODEL_NOT_READY"
    assert body["message"] == "이미지 분석 모델이 준비되지 않았습니다."


def test_predict_unexpected_error_is_500_vision_inference_error(client, stub_model):
    stub_model(raises=RuntimeError)

    with pytest.raises(RuntimeError):
        # TestClient re-raises server exceptions by default; the production
        # handler (registered for Exception) maps them to 500.
        client.post("/internal/v1/predict", files={"image": JPEG})


def test_predict_unexpected_error_maps_to_500_when_handler_runs(stub_model):
    stub_model(raises=RuntimeError)
    with TestClient(vision_main.app, raise_server_exceptions=False) as c:
        resp = c.post("/internal/v1/predict", files={"image": JPEG})

    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "VISION_INFERENCE_ERROR"
    assert body["message"] == "이미지 분석 중 오류가 발생했습니다."


def test_predict_rejects_empty_file(client, stub_model):
    stub_model()
    resp = client.post(
        "/internal/v1/predict", files={"image": ("empty.jpg", b"", "image/jpeg")}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "IMAGE_EMPTY"


def test_predict_rejects_unsupported_type(client, stub_model):
    stub_model()
    resp = client.post(
        "/internal/v1/predict", files={"image": ("a.gif", b"GIF89a", "image/gif")}
    )
    assert resp.status_code == 415
    assert resp.json()["code"] == "IMAGE_TYPE_UNSUPPORTED"


def test_predict_rejects_oversized_file(client, stub_model, monkeypatch):
    stub_model()
    monkeypatch.setattr(settings, "max_image_size_mb", 1)

    resp = client.post(
        "/internal/v1/predict",
        files={"image": ("big.jpg", b"x" * (2 * 1024 * 1024), "image/jpeg")},
    )

    assert resp.status_code == 413
    assert resp.json()["code"] == "IMAGE_TOO_LARGE"


def test_predict_requires_image_field(client, stub_model):
    stub_model()
    resp = client.post("/internal/v1/predict")
    assert resp.status_code == 422
    assert resp.json()["code"] == "REQUEST_VALIDATION_ERROR"


# --- GET /internal/v1/classes ---------------------------------------------


def test_classes_returns_full_86_class_taxonomy(client, stub_model):
    stub_model()

    resp = client.get("/internal/v1/classes")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"model_version", "classes"}
    assert isinstance(body["model_version"], str)

    classes = body["classes"]
    assert len(classes) == 86
    assert all(set(c) == {"class_id", "major_category", "minor_category"} for c in classes)
    # Sorted by class_id, contiguous 0..85 — the ids the Backend stores.
    assert [c["class_id"] for c in classes] == list(range(86))
    assert classes[0] == {"class_id": 0, "major_category": "고철류", "minor_category": "고철"}
    assert classes[85] == {"class_id": 85, "major_category": "형광등", "minor_category": "환형"}


def test_classes_returns_503_when_model_not_loaded(client, stub_model):
    stub_model(ready=False)

    resp = client.get("/internal/v1/classes")

    assert resp.status_code == 503
    assert resp.json()["code"] == "VISION_MODEL_NOT_READY"


# --- GET /health -----------------------------------------------------------


def test_health_reports_model_state(client, stub_model):
    stub_model()

    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"status", "model_loaded", "model_version"}
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert isinstance(body["model_version"], str)


def test_health_nulls_model_version_when_not_loaded(client, stub_model):
    stub_model(ready=False)

    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["model_loaded"] is False
    assert body["model_version"] is None  # Nullable=Yes (섹션 14.3)
