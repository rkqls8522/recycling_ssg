"""Temporary audit probe: DB schema vs spec section 18 / DR-01..DR-15."""
from __future__ import annotations

import json

from sqlalchemy import inspect, text

from core.database import engine
from models.feedback import Feedback
from models.image import Image
from models.waste_class import WasteClass


def test_tables_and_columns(db_session):
    insp = inspect(engine)
    print("TABLES:", sorted(insp.get_table_names()))
    for t in sorted(insp.get_table_names()):
        cols = [(c["name"], str(c["type"]), c["nullable"]) for c in insp.get_columns(t)]
        print(f"COLS[{t}]:", cols)
        print(f"UNIQUE[{t}]:", insp.get_unique_constraints(t))
        print(f"FK[{t}]:", [(fk["constrained_columns"], fk["referred_table"], fk["referred_columns"]) for fk in insp.get_foreign_keys(t)])


def test_class_zero_exists(db_session):
    wc0 = db_session.get(WasteClass, 0)
    print("CLASS 0:", None if wc0 is None else (wc0.class_id, wc0.major_category, wc0.minor_category))
    n = db_session.query(WasteClass).count()
    print("WASTE_CLASS COUNT:", n)
    mx = db_session.execute(text("SELECT MIN(class_id), MAX(class_id) FROM waste_classes")).fetchone()
    print("CLASS ID RANGE:", mx)


def test_class_zero_endpoints(client, db_session, signup_and_login, monkeypatch):
    headers, user_id = signup_and_login()
    client.patch("/api/v1/users/me/region", json={"region_id": 23}, headers=headers)

    fav0 = client.post("/api/v1/favorites", json={"class_id": 0}, headers=headers)
    print("FAVORITE class_id=0:", fav0.status_code, json.dumps(fav0.json(), ensure_ascii=False))

    import api.disposal as disposal_module

    monkeypatch.setattr(
        disposal_module,
        "get_disposal_info_or_raise",
        lambda waste_class, region: {
            "disposal_day": "월요일",
            "start_time": None,
            "end_time": None,
            "disposal_method": None,
        },
    )
    sch0 = client.get("/api/v1/disposal/schedule", params={"class_id": 0}, headers=headers)
    print("SCHEDULE class_id=0:", sch0.status_code, json.dumps(sch0.json(), ensure_ascii=False))

    # select-candidate with class_id 0 present in the snapshot
    from models.feedback_candidate import FeedbackCandidate

    image = Image(user_id=user_id, s3_key="feedback/test/zero.jpg")
    db_session.add(image)
    db_session.flush()
    fb = Feedback(
        user_id=user_id,
        image_id=image.image_id,
        predicted_class_id=22,
        predicted_score=0.9,
        bbox_x1=0.1, bbox_y1=0.1, bbox_x2=0.9, bbox_y2=0.9,
        model_version="test-model-v1",
    )
    db_session.add(fb)
    db_session.flush()
    db_session.add(FeedbackCandidate(feedback_id=fb.feedback_id, class_id=0, score=0.3, rank=2))
    db_session.commit()
    fid = fb.feedback_id
    print("FEEDBACK DEFAULTS:", fb.is_correct, fb.final_class_id, fb.correction_source)

    sel = client.post(
        f"/api/v1/feedback/{fid}/select-candidate", json={"class_id": 0}, headers=headers
    )
    print("SELECT-CANDIDATE class_id=0:", sel.status_code, json.dumps(sel.json(), ensure_ascii=False))
