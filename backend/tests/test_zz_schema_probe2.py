"""Temporary audit probe 2: datetime serialization format (spec 3.3)."""
from __future__ import annotations

import json


def test_datetime_format(client, signup_and_login):
    headers, _ = signup_and_login()
    me = client.get("/api/v1/users/me", headers=headers)
    print("ME BODY:", json.dumps(me.json(), ensure_ascii=False))

    fav = client.post("/api/v1/favorites", json={"class_id": 22}, headers=headers)
    print("FAV CREATE:", fav.status_code, json.dumps(fav.json(), ensure_ascii=False))
    lst = client.get("/api/v1/favorites", headers=headers)
    print("FAV LIST:", json.dumps(lst.json(), ensure_ascii=False))
