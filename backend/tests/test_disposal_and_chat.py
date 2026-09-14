"""Disposal-schedule and chat endpoint tests. External calls (공공데이터 API,
Gemini) are monkeypatched out so the suite stays hermetic."""

from __future__ import annotations

import api.chat as chat_module
import api.disposal as disposal_module
from models.feedback import Feedback
from models.image import Image


def test_disposal_schedule_requires_region_then_succeeds(client, signup_and_login, monkeypatch):
    headers, _ = signup_and_login()

    unknown_class = client.get("/api/v1/disposal/schedule", params={"class_id": 999999}, headers=headers)
    assert unknown_class.status_code == 404
    assert unknown_class.json()["code"] == "CLASS_NOT_FOUND"

    no_region = client.get("/api/v1/disposal/schedule", params={"class_id": 22}, headers=headers)
    assert no_region.status_code == 409
    assert no_region.json()["code"] == "USER_REGION_REQUIRED"

    client.patch("/api/v1/users/me/region", json={"region_id": 23}, headers=headers)

    monkeypatch.setattr(
        disposal_module,
        "get_disposal_info_or_raise",
        lambda waste_class, region: {
            "disposal_day": "화, 목",
            "start_time": "18:00",
            "end_time": "24:00",
            "disposal_method": "내용물을 비운 후 배출합니다.",
        },
    )

    ok = client.get("/api/v1/disposal/schedule", params={"class_id": 22}, headers=headers)
    assert ok.status_code == 200
    body = ok.json()
    assert body["disposal_day"] == "화, 목"
    assert body["region"]["region_id"] == 23


def test_chat_ownership_and_region_checks(client, db_session, signup_and_login, monkeypatch):
    headers, user_id = signup_and_login()

    image = Image(s3_key="feedback/test/chat.jpg")
    db_session.add(image)
    db_session.flush()
    feedback = Feedback(
        user_id=user_id,
        image_id=image.image_id,
        predicted_class_id=22,
        predicted_score=0.9,
        bbox_x1=0.1,
        bbox_y1=0.1,
        bbox_x2=0.9,
        bbox_y2=0.9,
        model_version="test-model-v1",
    )
    db_session.add(feedback)
    db_session.commit()

    missing = client.post(
        "/api/v1/chat", json={"feedback_id": 999999, "message": "질문"}, headers=headers
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "FEEDBACK_NOT_FOUND"

    other_headers, _ = signup_and_login()
    forbidden = client.post(
        "/api/v1/chat",
        json={"feedback_id": feedback.feedback_id, "message": "질문"},
        headers=other_headers,
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "FEEDBACK_FORBIDDEN"

    no_region = client.post(
        "/api/v1/chat", json={"feedback_id": feedback.feedback_id, "message": "질문"}, headers=headers
    )
    assert no_region.status_code == 409
    assert no_region.json()["code"] == "USER_REGION_REQUIRED"

    client.patch("/api/v1/users/me/region", json={"region_id": 23}, headers=headers)
    monkeypatch.setattr(
        chat_module, "answer_question", lambda db, *, user, feedback, message: ("테스트 답변", [])
    )

    ok = client.post(
        "/api/v1/chat", json={"feedback_id": feedback.feedback_id, "message": "질문"}, headers=headers
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["answer"] == "테스트 답변"
    assert body["feedback_id"] == feedback.feedback_id
