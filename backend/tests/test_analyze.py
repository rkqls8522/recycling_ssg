"""POST /api/v1/analyze contract tests (섹션 8.1 + 19).

The Vision Server, S3 and the 공공데이터 API are all replaced with fakes so
the full orchestration — including the RETAKE_REQUIRED gates, the
transaction rollback + S3 compensating delete, and the "external API
failure must not fail the analysis" rule — is asserted without any
external dependency.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api import analyze as analyze_api
from core.config import settings
from models.feedback import Feedback
from models.feedback_candidate import FeedbackCandidate
from models.image import Image
from schemas.common import CandidateScoreOut
from schemas.vision import BBox, InternalMeta, VisionPredictResponse
from services import storage, vision_client


def _make_test_jpeg(width: int = 64, height: int = 48) -> bytes:
    """A genuinely decodable JPEG -- analyze.py now decodes+resizes every
    upload (services.image_processing) before calling Vision/S3, so test
    fixtures can no longer be arbitrary placeholder bytes."""
    buffer = io.BytesIO()
    PILImage.new("RGB", (width, height), color=(120, 180, 90)).save(buffer, format="JPEG")
    return buffer.getvalue()

PLASTIC_MAIN = 14  # 플라스틱류/플라스틱
PLASTIC_TOY = 15  # 플라스틱류/장난감


def _prediction(top_score: float = 0.8123) -> VisionPredictResponse:
    return VisionPredictResponse(
        major_category="플라스틱류",
        minor_category="플라스틱",
        class_id=PLASTIC_MAIN,
        score=top_score,
        # Top-1(PLASTIC_MAIN)을 제외한 "다른 후보"만 담는다.
        candidate_scores=[
            CandidateScoreOut(class_id=PLASTIC_TOY, category="플라스틱류_장난감", score=0.1211),
        ],
        internal_meta=InternalMeta(
            bbox=BBox(x1=0.25, y1=0.18, x2=0.76, y2=0.88),
            model_version="yolo26n-recycling-test",
            inference_ms=31.7,
        ),
    )


@pytest.fixture
def image_file():
    return {"image": ("photo.jpg", _make_test_jpeg(), "image/jpeg")}


@pytest.fixture
def authed_with_region(client: TestClient, signup_and_login):
    headers, user_id = signup_and_login()
    resp = client.patch("/api/v1/users/me/region", json={"region_id": 23}, headers=headers)
    assert resp.status_code == 200, resp.text
    return headers, user_id


@pytest.fixture
def fake_externals(monkeypatch):
    """Happy-path fakes for Vision + S3 + disposal lookup, with call recording."""
    calls = {"upload": [], "delete": [], "predict": 0}

    def fake_predict(**kwargs):
        calls["predict"] += 1
        return calls.get("prediction") or _prediction()

    def fake_upload(*, file_bytes, content_type, user_id, extension):
        calls["upload"].append((len(file_bytes), content_type, user_id, extension))
        return f"feedback/2026/09/12/{user_id}-test.{extension}"

    monkeypatch.setattr(vision_client, "predict", fake_predict)
    monkeypatch.setattr(storage, "upload_image", fake_upload)
    monkeypatch.setattr(storage, "delete_object", lambda key: calls["delete"].append(key))
    monkeypatch.setattr(
        analyze_api, "get_disposal_info_or_warn", lambda waste_class, region: ("화, 목", [])
    )
    return calls


# --- SUCCESS ---------------------------------------------------------------


def test_analyze_success_returns_full_contract_and_persists_rows(
    client, authed_with_region, fake_externals, image_file, db_session: Session
):
    headers, user_id = authed_with_region

    resp = client.post("/api/v1/analyze", files=image_file, headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["status"] == "SUCCESS"
    assert body["major_category"] == "플라스틱류"
    assert body["minor_category"] == "플라스틱"
    assert body["class_id"] == PLASTIC_MAIN
    assert body["score"] == pytest.approx(0.8123)
    assert body["disposal_day"] == "화, 목"
    assert body["warnings"] == []
    assert isinstance(body["image_id"], int)
    assert isinstance(body["feedback_id"], int)

    # Region object carries exactly the three spec fields (섹션 4.2).
    assert set(body["user_region"]) == {"region_id", "sido_name", "sgg_name"}
    assert body["user_region"] == {
        "region_id": 23,
        "sido_name": "서울특별시",
        "sgg_name": "강남구",
    }

    # CandidateScore objects -- Top-1(class_id/score, 위에서 이미 확인)은 빠지고
    # "다른 후보"만 남는다, score 내림차순 (SR-07).
    scores = body["candidate_scores"]
    assert [s["class_id"] for s in scores] == [PLASTIC_TOY]
    assert all(set(s) == {"class_id", "category", "score"} for s in scores)
    assert scores == sorted(scores, key=lambda s: s["score"], reverse=True)

    # Persistence: images + feedback + Top-K snapshot (섹션 19).
    image_row = db_session.get(Image, body["image_id"])
    assert image_row is not None
    assert image_row.s3_key.startswith("feedback/")
    assert "http" not in image_row.s3_key  # never a presigned URL (섹션 15.2)
    # 업로드는 항상 재인코딩되어 저장된다 (기본 JPEG, services.image_processing).
    assert image_row.content_type == "image/jpeg"
    assert image_row.s3_key.endswith(".jpg")

    feedback_row = db_session.get(Feedback, body["feedback_id"])
    assert feedback_row.user_id == user_id
    assert feedback_row.predicted_class_id == PLASTIC_MAIN
    assert feedback_row.predicted_score == pytest.approx(0.8123)
    assert feedback_row.model_version == "yolo26n-recycling-test"
    # BBox stored as 0~1 normalized XYXY (섹션 3.3, 20).
    assert (feedback_row.bbox_x1, feedback_row.bbox_y1) == (0.25, 0.18)
    assert (feedback_row.bbox_x2, feedback_row.bbox_y2) == (0.76, 0.88)
    assert feedback_row.bbox_x1 < feedback_row.bbox_x2
    assert feedback_row.bbox_y1 < feedback_row.bbox_y2
    # Untouched feedback keeps the NULL triple (SR-23 / DR-13 / DR-14).
    assert feedback_row.final_class_id is None
    assert feedback_row.is_correct is None
    assert feedback_row.correction_source is None
    # major/minor strings are never stored on feedback (섹션 1, 20).
    assert not hasattr(feedback_row, "major_category")
    assert not hasattr(feedback_row, "minor_category")

    candidates = (
        db_session.query(FeedbackCandidate)
        .filter(FeedbackCandidate.feedback_id == body["feedback_id"])
        .order_by(FeedbackCandidate.rank)
        .all()
    )
    # feedback_candidates에는 이제 "다른 후보"만 저장된다 (PLASTIC_MAIN은
    # feedback.predicted_class_id에 이미 저장됨). rank는 1부터 다시 매김.
    assert [(c.class_id, c.rank) for c in candidates] == [
        (PLASTIC_TOY, 1),
    ]


def test_analyze_succeeds_with_warning_when_public_api_fails(
    client, authed_with_region, fake_externals, image_file, monkeypatch
):
    """섹션 15.1: 공공데이터 API 실패는 분석 저장을 롤백하지 않고 warnings 로 반환."""
    headers, _ = authed_with_region
    monkeypatch.setattr(
        analyze_api,
        "get_disposal_info_or_warn",
        lambda waste_class, region: (None, ["PUBLIC_WASTE_UNAVAILABLE"]),
    )

    resp = client.post("/api/v1/analyze", files=image_file, headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["disposal_day"] is None
    assert body["warnings"] == ["PUBLIC_WASTE_UNAVAILABLE"]
    assert isinstance(body["feedback_id"], int)  # analysis still persisted


# --- RETAKE_REQUIRED (HTTP 200) --------------------------------------------


def test_analyze_low_confidence_returns_retake_but_still_persists_rows(
    client, authed_with_region, fake_externals, image_file, db_session: Session
):
    """신뢰도가 낮아도 재학습용 데이터는 SUCCESS 경로와 동일하게 저장하고,
    사용자 응답은 그대로 RETAKE_REQUIRED(스코어 포함)로 돌려준다."""
    headers, user_id = authed_with_region
    fake_externals["prediction"] = _prediction(top_score=0.42)

    resp = client.post("/api/v1/analyze", files=image_file, headers=headers)

    assert resp.status_code == 200, resp.text  # business branch, not an HTTP error
    body = resp.json()
    assert body["status"] == "RETAKE_REQUIRED"
    assert body["code"] == "AI_LOW_CONFIDENCE"
    assert body["message"] == "분석 신뢰도가 낮습니다. 물체를 중앙에 선명하게 두고 다시 촬영해주세요."
    assert body["threshold"] == 0.5
    assert body["score"] == 0.42
    assert body["request_id"] == resp.headers["X-Request-ID"]
    # 응답 계약은 그대로 -- image_id/feedback_id는 노출하지 않는다.
    assert "image_id" not in body
    assert "feedback_id" not in body

    assert len(fake_externals["upload"]) == 1  # S3에는 그대로 업로드됨

    feedback_row = (
        db_session.query(Feedback).filter(Feedback.user_id == user_id).one()
    )
    assert feedback_row.predicted_class_id == PLASTIC_MAIN
    assert feedback_row.predicted_score == pytest.approx(0.42)
    # 미응답 상태(NULL triple)로 저장되어 chk_feedback_result_state를 만족한다.
    assert feedback_row.final_class_id is None
    assert feedback_row.is_correct is None
    assert feedback_row.correction_source is None

    image_row = db_session.get(Image, feedback_row.image_id)
    assert image_row is not None
    assert image_row.s3_key.startswith("feedback/")

    candidates = (
        db_session.query(FeedbackCandidate)
        .filter(FeedbackCandidate.feedback_id == feedback_row.feedback_id)
        .all()
    )
    assert [(c.class_id, c.rank) for c in candidates] == [(PLASTIC_TOY, 1)]


def test_analyze_no_main_object_returns_retake_without_threshold(
    client, authed_with_region, fake_externals, image_file, monkeypatch, db_session: Session
):
    headers, user_id = authed_with_region

    def raise_no_main_object(**kwargs):
        raise vision_client.VisionNoMainObjectError

    monkeypatch.setattr(vision_client, "predict", raise_no_main_object)
    before = db_session.query(Feedback).filter(Feedback.user_id == user_id).count()

    resp = client.post("/api/v1/analyze", files=image_file, headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "RETAKE_REQUIRED"
    assert body["code"] == "AI_NO_MAIN_OBJECT"
    assert body["message"] == "분류할 물체를 화면 중앙에 위치시킨 뒤 다시 촬영해주세요."
    assert body["threshold"] is None
    assert body["score"] is None
    assert body["request_id"]

    assert fake_externals["upload"] == []
    assert db_session.query(Feedback).filter(Feedback.user_id == user_id).count() == before


# --- Precondition / validation errors --------------------------------------


def test_analyze_requires_auth(client, image_file):
    resp = client.post("/api/v1/analyze", files=image_file)
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_REQUIRED"


def test_analyze_requires_region_with_endpoint_specific_message(
    client, signup_and_login, fake_externals, image_file
):
    headers, _ = signup_and_login()  # no region selected

    resp = client.post("/api/v1/analyze", files=image_file, headers=headers)

    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "USER_REGION_REQUIRED"
    assert body["message"] == "분석 전에 거주 지역을 선택해주세요."
    assert fake_externals["predict"] == 0  # never reached the Vision server


def test_analyze_rejects_unsupported_content_type(client, authed_with_region, fake_externals):
    headers, _ = authed_with_region
    resp = client.post(
        "/api/v1/analyze",
        files={"image": ("doc.gif", b"GIF89a-bytes", "image/gif")},
        headers=headers,
    )
    assert resp.status_code == 415
    body = resp.json()
    assert body["code"] == "IMAGE_TYPE_UNSUPPORTED"
    assert body["message"] == "지원하지 않는 이미지 형식입니다. JPG, PNG 또는 WEBP 이미지를 사용해주세요."


def test_analyze_rejects_empty_file(client, authed_with_region, fake_externals):
    headers, _ = authed_with_region
    resp = client.post(
        "/api/v1/analyze",
        files={"image": ("empty.jpg", b"", "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "IMAGE_EMPTY"
    assert resp.json()["message"] == "업로드된 이미지가 비어 있습니다."


def test_analyze_rejects_oversized_file(client, authed_with_region, fake_externals, monkeypatch):
    headers, _ = authed_with_region
    monkeypatch.setattr(settings, "max_image_size_mb", 1)

    resp = client.post(
        "/api/v1/analyze",
        files={"image": ("big.jpg", b"x" * (2 * 1024 * 1024), "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 413
    assert resp.json()["code"] == "IMAGE_TOO_LARGE"


def test_analyze_missing_image_field_is_validation_error(client, authed_with_region):
    headers, _ = authed_with_region
    resp = client.post("/api/v1/analyze", headers=headers)
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "REQUEST_VALIDATION_ERROR"
    assert body["details"]  # field-level detail array (섹션 16.1)


# --- Downstream failures ---------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "code", "message"),
    [
        (502, "VISION_UNAVAILABLE", "이미지 분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."),
        (504, "VISION_TIMEOUT", "이미지 분석 시간이 초과되었습니다. 다시 시도해주세요."),
        (502, "VISION_BAD_RESPONSE", "이미지 분석 결과를 처리할 수 없습니다."),
        (503, "VISION_MODEL_NOT_READY", "이미지 분석 모델이 준비되지 않았습니다."),
    ],
)
def test_analyze_propagates_vision_failures(
    client, authed_with_region, fake_externals, image_file, monkeypatch, status_code, code, message
):
    from core.exceptions import AppError

    headers, _ = authed_with_region

    def raise_app_error(**kwargs):
        raise AppError(status_code=status_code, code=code, message=message)

    monkeypatch.setattr(vision_client, "predict", raise_app_error)

    resp = client.post("/api/v1/analyze", files=image_file, headers=headers)

    assert resp.status_code == status_code
    body = resp.json()
    assert body["code"] == code
    assert body["message"] == message
    assert fake_externals["upload"] == []  # nothing stored


def test_analyze_s3_failure_leaves_no_db_row(
    client, authed_with_region, fake_externals, image_file, monkeypatch, db_session: Session
):
    from core.exceptions import AppError

    headers, user_id = authed_with_region

    def raise_upload_failed(**kwargs):
        raise AppError(
            status_code=502,
            code="S3_UPLOAD_FAILED",
            message="이미지 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        )

    monkeypatch.setattr(storage, "upload_image", raise_upload_failed)
    before = db_session.query(Feedback).filter(Feedback.user_id == user_id).count()

    resp = client.post("/api/v1/analyze", files=image_file, headers=headers)

    assert resp.status_code == 502
    assert resp.json()["code"] == "S3_UPLOAD_FAILED"
    assert db_session.query(Feedback).filter(Feedback.user_id == user_id).count() == before


def test_analyze_db_failure_rolls_back_and_compensates_s3(
    client, authed_with_region, fake_externals, image_file, monkeypatch, db_session: Session
):
    """섹션 19: DB Transaction 실패 -> ROLLBACK + S3 보상 삭제."""
    headers, user_id = authed_with_region

    def failing_commit(self):
        raise SQLAlchemyError("simulated commit failure")

    monkeypatch.setattr(Session, "commit", failing_commit)
    before = db_session.query(Feedback).filter(Feedback.user_id == user_id).count()

    resp = client.post("/api/v1/analyze", files=image_file, headers=headers)

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "DATABASE_ERROR"
    assert body["message"] == "데이터베이스 처리 중 오류가 발생했습니다."

    # The uploaded object was deleted again (compensating action).
    assert len(fake_externals["upload"]) == 1
    _, _, uploaded_user_id, extension = fake_externals["upload"][0]
    expected_key = f"feedback/2026/09/12/{uploaded_user_id}-test.{extension}"
    assert fake_externals["delete"] == [expected_key]

    monkeypatch.undo()  # restore Session.commit before touching the DB again
    assert db_session.query(Feedback).filter(Feedback.user_id == user_id).count() == before
