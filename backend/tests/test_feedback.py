"""Feedback confirm/select-candidate flow, exercised against a Feedback row
inserted directly (bypassing /analyze, which needs S3 + the Vision Server)."""

from __future__ import annotations

import pytest

from models.feedback import Feedback
from models.feedback_candidate import FeedbackCandidate
from models.image import Image


@pytest.fixture
def seeded_feedback(db_session, signup_and_login):
    headers, user_id = signup_and_login()

    image = Image(user_id=user_id, s3_key="feedback/test/fake.jpg")
    db_session.add(image)
    db_session.flush()

    feedback = Feedback(
        user_id=user_id,
        image_id=image.image_id,
        predicted_class_id=22,  # 플라스틱류/욕실용품
        predicted_score=0.81,
        bbox_x1=0.1,
        bbox_y1=0.1,
        bbox_x2=0.9,
        bbox_y2=0.9,
        model_version="test-model-v1",
    )
    db_session.add(feedback)
    db_session.flush()

    for rank, (class_id, score) in enumerate([(22, 0.81), (15, 0.12), (31, 0.04)], start=1):
        db_session.add(
            FeedbackCandidate(feedback_id=feedback.feedback_id, class_id=class_id, score=score, rank=rank)
        )
    db_session.commit()

    return headers, feedback.feedback_id


def test_confirm_feedback(client, seeded_feedback):
    headers, feedback_id = seeded_feedback
    resp = client.post(f"/api/v1/feedback/{feedback_id}/confirm", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_correct"] is True
    assert body["final_class_id"] == 22
    assert body["correction_source"] is None

    already = client.post(f"/api/v1/feedback/{feedback_id}/confirm", headers=headers)
    assert already.status_code == 409
    assert already.json()["code"] == "FEEDBACK_ALREADY_COMPLETED"


def test_select_candidate_flow(client, seeded_feedback):
    headers, feedback_id = seeded_feedback

    same_as_prediction = client.post(
        f"/api/v1/feedback/{feedback_id}/select-candidate", json={"class_id": 22}, headers=headers
    )
    assert same_as_prediction.status_code == 400
    assert same_as_prediction.json()["code"] == "FEEDBACK_SAME_AS_PREDICTION"

    invalid_candidate = client.post(
        f"/api/v1/feedback/{feedback_id}/select-candidate", json={"class_id": 9999}, headers=headers
    )
    assert invalid_candidate.status_code == 400
    assert invalid_candidate.json()["code"] == "FEEDBACK_INVALID_CANDIDATE"

    ok = client.post(
        f"/api/v1/feedback/{feedback_id}/select-candidate", json={"class_id": 15}, headers=headers
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["is_correct"] is False
    assert body["final_class_id"] == 15
    assert body["correction_source"] == "USER"


def test_feedback_not_found_and_forbidden(client, seeded_feedback, signup_and_login):
    _headers, feedback_id = seeded_feedback

    not_found = client.post("/api/v1/feedback/99999999/confirm", headers=_headers)
    assert not_found.status_code == 404
    assert not_found.json()["code"] == "FEEDBACK_NOT_FOUND"

    other_headers, _ = signup_and_login()
    forbidden = client.post(f"/api/v1/feedback/{feedback_id}/confirm", headers=other_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "FEEDBACK_FORBIDDEN"
