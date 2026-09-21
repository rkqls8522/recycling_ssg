"""POST /api/v1/feedback/{feedback_id}/not-in-list — RAG 재분류 (섹션 9.3).

RAG 서비스 호출(services.disposal_service.reclassify_or_raise)과 S3 download는
전부 faked 되어 있어서, 문서화된 모든 성공/실패 매핑을 실제 RAG 서버 없이
검증한다. (구 Gemini 단독 재분류 방식을 대체한 이후 버전 — 섹션 9.3)
"""

from __future__ import annotations

import pytest

from api import feedback as feedback_api
from core.exceptions import AppError
from models.feedback import Feedback
from models.feedback_candidate import FeedbackCandidate
from models.image import Image
from services import disposal_service, storage

STEEL_SCRAP = 0  # 고철류/고철


def _reclassify_result(
    *, major: str | None, minor: str | None, needs_retake: bool = False,
    national_rule: dict | None = None, region_rule: dict | None = None,
) -> dict:
    """RAG 서비스의 실제 응답(rag/api/schemas.py::ReclassifyResponse)과 같은 모양."""
    disposal_result = None
    if major is not None and minor is not None:
        disposal_result = {
            "item": None,
            "major_category": major,
            "minor_category": minor,
            "national_rule": national_rule,
            "region_rule": region_rule,
            "has_region_exception": region_rule is not None,
        }
    return {
        "major_category": major,
        "minor_category": minor,
        "disposal_result": disposal_result,
        "needs_retake": needs_retake,
    }


@pytest.fixture
def seeded_feedback(db_session, signup_and_login, client):
    headers, user_id = signup_and_login()
    # not_in_list은 region_id가 있어야 진행되므로(USER_REGION_REQUIRED) 미리 설정.
    resp = client.patch("/api/v1/users/me/region", json={"region_id": 23}, headers=headers)
    assert resp.status_code == 200, resp.text

    image = Image(s3_key="feedback/2026/09/12/fake.jpg")
    db_session.add(image)
    db_session.flush()

    feedback = Feedback(
        user_id=user_id,
        image_id=image.image_id,
        predicted_class_id=4,  # 비닐/비닐
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
        FeedbackCandidate(feedback_id=feedback.feedback_id, class_id=4, score=0.62, rank=1)
    )
    db_session.commit()

    return headers, feedback.feedback_id


@pytest.fixture
def fake_s3_download(monkeypatch):
    monkeypatch.setattr(storage, "download_image", lambda key: b"\xff\xd8\xff\xe0jpeg")


@pytest.fixture
def fake_disposal_lookup(monkeypatch):
    """disposal_day best-effort 조회를 결정적인 값으로 고정 (섹션 15.1 패턴)."""
    monkeypatch.setattr(
        feedback_api, "get_disposal_info_or_warn", lambda waste_class, region: ("화, 목", [])
    )


def test_not_in_list_success_sets_final_class_and_disposal_info(
    client, seeded_feedback, fake_s3_download, fake_disposal_lookup, monkeypatch, db_session
):
    headers, feedback_id = seeded_feedback
    monkeypatch.setattr(
        disposal_service,
        "reclassify_or_raise",
        lambda **kwargs: _reclassify_result(
            major="고철류",
            minor="고철",
            national_rule={"source": "기후에너지환경부", "method": "이물질을 제거하여 배출"},
        ),
    )

    resp = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["feedback_id"] == feedback_id
    assert body["is_correct"] is False
    assert body["final_class_id"] == STEEL_SCRAP
    assert body["correction_source"] == "GEMINI"
    assert body["major_category"] == "고철류"
    assert body["minor_category"] == "고철"
    assert body["disposal_day"] == "화, 목"
    assert body["national_rule"] == {
        "source": "기후에너지환경부",
        "method": "이물질을 제거하여 배출",
    }
    assert body["region_rule"] is None
    assert body["message"] == "추가 이미지 분석 결과로 수정되었습니다."

    row = db_session.get(Feedback, feedback_id)
    db_session.refresh(row)
    assert row.final_class_id == STEEL_SCRAP
    assert row.is_correct is False
    assert row.correction_source == "GEMINI"
    # feedback_candidates is an analysis-time snapshot: unchanged (섹션 9.2/9.3).
    assert (
        db_session.query(FeedbackCandidate)
        .filter(FeedbackCandidate.feedback_id == feedback_id)
        .count()
        == 1
    )


def test_not_in_list_returns_retake_when_judge_loop_fails(
    client, seeded_feedback, fake_s3_download, monkeypatch, db_session
):
    """RAG 재분류 그래프가 judge 검증 재시도를 소진하면(needs_retake=True)
    200 RETAKE_REQUIRED / AI_RECLASSIFY_FAILED 로 응답하고, feedback은 그대로
    미완료 상태로 남는다."""
    headers, feedback_id = seeded_feedback
    monkeypatch.setattr(
        disposal_service,
        "reclassify_or_raise",
        lambda **kwargs: _reclassify_result(major=None, minor=None, needs_retake=True),
    )

    resp = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "status": "RETAKE_REQUIRED",
        "code": "AI_RECLASSIFY_FAILED",
        "message": "재분류에 실패했습니다. 사진을 다시 촬영해 업로드해주세요.",
    }

    row = db_session.get(Feedback, feedback_id)
    assert row.final_class_id is None
    assert row.is_correct is None
    assert row.correction_source is None


def test_not_in_list_rejects_category_unknown_to_waste_classes(
    client, seeded_feedback, fake_s3_download, monkeypatch
):
    """RAG 결과는 waste_classes 에 실제로 존재하는 대/소분류 조합으로 제한 (섹션 9.3 / SR-20)."""
    headers, feedback_id = seeded_feedback
    monkeypatch.setattr(
        disposal_service,
        "reclassify_or_raise",
        lambda **kwargs: _reclassify_result(major="없는대분류", minor="없는소분류"),
    )

    resp = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)

    assert resp.status_code == 502
    assert resp.json()["code"] == "RAG_BAD_RESPONSE"


@pytest.mark.parametrize(
    ("status_code", "code", "message"),
    [
        (
            504,
            "RAG_RECLASSIFY_TIMEOUT",
            "추가 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요.",
        ),
        (
            502,
            "RAG_SERVICE_UNAVAILABLE",
            "추가 이미지 분석 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ),
        (
            502,
            "RAG_BAD_RESPONSE",
            "추가 이미지 분석 결과를 처리할 수 없습니다.",
        ),
    ],
)
def test_not_in_list_maps_every_reclassify_failure(
    client, seeded_feedback, fake_s3_download, monkeypatch, status_code, code, message
):
    headers, feedback_id = seeded_feedback

    def raise_error(**kwargs):
        raise AppError(status_code=status_code, code=code, message=message)

    monkeypatch.setattr(disposal_service, "reclassify_or_raise", raise_error)

    resp = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)

    assert resp.status_code == status_code
    body = resp.json()
    assert body["code"] == code
    assert body["message"] == message


def test_not_in_list_maps_s3_download_failure(client, seeded_feedback, monkeypatch):
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


def test_not_in_list_requires_region(client, db_session, signup_and_login):
    """region_id 미설정 사용자는 S3/RAG 호출 전에 409로 막힌다 (다른 엔드포인트와 동일 패턴)."""
    headers, user_id = signup_and_login()  # 지역 선택 안 함

    image = Image(s3_key="feedback/2026/09/12/no-region.jpg")
    db_session.add(image)
    db_session.flush()
    feedback = Feedback(
        user_id=user_id,
        image_id=image.image_id,
        predicted_class_id=4,
        predicted_score=0.62,
        bbox_x1=0.1,
        bbox_y1=0.1,
        bbox_x2=0.9,
        bbox_y2=0.9,
        model_version="test-model-v1",
    )
    db_session.add(feedback)
    db_session.commit()

    resp = client.post(f"/api/v1/feedback/{feedback.feedback_id}/not-in-list", headers=headers)

    assert resp.status_code == 409
    assert resp.json()["code"] == "USER_REGION_REQUIRED"


def test_not_in_list_rejects_already_completed(
    client, seeded_feedback, fake_s3_download, fake_disposal_lookup, monkeypatch
):
    headers, feedback_id = seeded_feedback
    monkeypatch.setattr(
        disposal_service,
        "reclassify_or_raise",
        lambda **kwargs: _reclassify_result(major="고철류", minor="고철"),
    )

    first = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)
    assert first.status_code == 200

    second = client.post(f"/api/v1/feedback/{feedback_id}/not-in-list", headers=headers)
    assert second.status_code == 409
    assert second.json()["code"] == "FEEDBACK_ALREADY_COMPLETED"


def test_not_in_list_ownership_and_auth(
    client, seeded_feedback, fake_s3_download, signup_and_login, monkeypatch
):
    headers, feedback_id = seeded_feedback
    monkeypatch.setattr(
        disposal_service,
        "reclassify_or_raise",
        lambda **kwargs: _reclassify_result(major="고철류", minor="고철"),
    )

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
