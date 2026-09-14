"""POST /api/v1/feedback/{feedback_id}/not-in-list — Gemini fallback (섹션 9.3).

S3 download and the Gemini call are faked, so every documented success and
failure mapping is asserted without an API key or network access.
"""

from __future__ import annotations

import pytest

from models.feedback import Feedback
from models.feedback_candidate import FeedbackCandidate
from models.image import Image
from services import gemini_service, storage

STEEL_FRYPAN = 7  # 고철류/프라이팬


@pytest.fixture
def seeded_feedback(db_session, signup_and_login):
    headers, user_id = signup_and_login()

    image = Image(s3_key="feedback/2026/09/12/fake.jpg")
    db_session.add(image)
    db_session.flush()

    feedback = Feedback(
        user_id=user_id,
        image_id=image.image_id,
        predicted_class_id=77,  # 플라스틱류/욕실용품
        predicted_score=0.62,
        bbox_x1=0.1,
        bbox_y1=0.1,
        bbox_x2=0.9,
        bbox_y2=0.9,
        model_version="test-model-v1",
    )
    db_session.add(feedback)
    db_session.flush()
    db_session.add(
        FeedbackCandidate(feedback_id=feedback.feedback_id, class_id=77, score=0.62, rank=1)
    )
    db_session.commit()

    return headers, feedback.feedback_id


@pytest.fixture
def fake_s3_download(monkeypatch):
    monkeypatch.setattr(storage, "download_image", lambda key: b"\xff\xd8\xff\xe0jpeg")


def test_not_in_list_success_sets_gemini_correction(
    client, seeded_feedback, fake_s3_download, monkeypatch, db_session
):
    headers, feedback_id = seeded_feedback
    monkeypatch.setattr(
        gemini_service, "reanalyze_image", lambda **kwargs: STEEL_FRYPAN
    )

    resp = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["feedback_id"] == feedback_id
    assert body["is_correct"] is False
    assert body["final_class_id"] == STEEL_FRYPAN
    assert body["correction_source"] == "GEMINI"
    assert body["major_category"] == "고철류"
    assert body["minor_category"] == "프라이팬"
    assert body["message"] == "추가 이미지 분석 결과로 수정되었습니다."

    row = db_session.get(Feedback, feedback_id)
    db_session.refresh(row)
    assert row.final_class_id == STEEL_FRYPAN
    assert row.is_correct is False
    assert row.correction_source == "GEMINI"
    # feedback_candidates is an analysis-time snapshot: unchanged (섹션 9.2/9.3).
    assert (
        db_session.query(FeedbackCandidate)
        .filter(FeedbackCandidate.feedback_id == feedback_id)
        .count()
        == 1
    )


def test_not_in_list_restricts_gemini_to_known_classes(
    client, seeded_feedback, fake_s3_download, monkeypatch
):
    """Gemini 결과는 waste_classes 에 존재하는 class_id 로 제한 (섹션 9.3 / SR-20)."""
    headers, feedback_id = seeded_feedback
    monkeypatch.setattr(gemini_service, "reanalyze_image", lambda **kwargs: 999999)

    resp = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)

    assert resp.status_code == 502
    assert resp.json()["code"] == "GEMINI_BAD_RESPONSE"


@pytest.mark.parametrize(
    ("error", "status_code", "code", "message"),
    [
        (
            gemini_service.GeminiNotConfiguredError,
            503,
            "GEMINI_NOT_CONFIGURED",
            "추가 이미지 분석 서비스가 설정되지 않았습니다.",
        ),
        (
            gemini_service.GeminiTimeoutError,
            504,
            "GEMINI_TIMEOUT",
            "추가 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요.",
        ),
        (
            gemini_service.GeminiBadResponseError,
            502,
            "GEMINI_BAD_RESPONSE",
            "추가 이미지 분석 결과를 처리할 수 없습니다.",
        ),
        (
            gemini_service.GeminiUnavailableError,
            502,
            "GEMINI_UNAVAILABLE",
            "추가 이미지 분석 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ),
    ],
)
def test_not_in_list_maps_every_gemini_failure(
    client, seeded_feedback, fake_s3_download, monkeypatch, error, status_code, code, message
):
    headers, feedback_id = seeded_feedback

    def raise_error(**kwargs):
        raise error

    monkeypatch.setattr(gemini_service, "reanalyze_image", raise_error)

    resp = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)

    assert resp.status_code == status_code
    body = resp.json()
    assert body["code"] == code
    assert body["message"] == message


def test_not_in_list_maps_s3_download_failure(client, seeded_feedback, monkeypatch):
    from core.exceptions import AppError

    headers, feedback_id = seeded_feedback

    def raise_download_failed(key):
        raise AppError(
            status_code=502,
            code="S3_DOWNLOAD_FAILED",
            message="원본 이미지를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.",
        )

    monkeypatch.setattr(storage, "download_image", raise_download_failed)

    resp = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)

    assert resp.status_code == 502
    assert resp.json()["code"] == "S3_DOWNLOAD_FAILED"


def test_not_in_list_rejects_already_completed(
    client, seeded_feedback, fake_s3_download, monkeypatch
):
    headers, feedback_id = seeded_feedback
    monkeypatch.setattr(gemini_service, "reanalyze_image", lambda **kwargs: STEEL_FRYPAN)

    first = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)
    assert first.status_code == 200

    second = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)
    assert second.status_code == 409
    assert second.json()["code"] == "FEEDBACK_ALREADY_COMPLETED"


def test_not_in_list_ownership_and_auth(
    client, seeded_feedback, fake_s3_download, signup_and_login, monkeypatch
):
    headers, feedback_id = seeded_feedback
    monkeypatch.setattr(gemini_service, "reanalyze_image", lambda **kwargs: STEEL_FRYPAN)

    anonymous = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list")
    assert anonymous.status_code == 401
    assert anonymous.json()["code"] == "AUTH_REQUIRED"

    other_headers, _ = signup_and_login()
    forbidden = client.post(
        f"/api/v1/feedback/{feedback_id}/not-in-list", headers=other_headers
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "FEEDBACK_FORBIDDEN"
    assert forbidden.json()["message"] == "해당 피드백에 접근할 권한이 없습니다."

    missing = client.post("/api/v1/feedback/99999999/not-in-list", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "FEEDBACK_NOT_FOUND"
