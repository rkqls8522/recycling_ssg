"""Datetime serialization contract (섹션 3.3: ISO 8601, 예 2026-09-11T09:00:00Z).

Timestamps must carry an explicit UTC designator. Without it a browser
parses "2026-09-11T23:46:35" as *local* time, silently shifting every
timestamp by the client's offset.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

ISO8601_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_signup_created_at_is_utc_iso8601(client, signup_and_login):
    email = f"dt-{uuid.uuid4().hex}@example.com"
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "Example123!"}
    )

    assert resp.status_code == 201
    created_at = resp.json()["created_at"]
    assert ISO8601_UTC.match(created_at), f"not ISO8601 UTC: {created_at!r}"


def test_signup_created_at_is_the_real_instant_not_shifted_by_kst_offset(client):
    """DB storage is KST (models.timestamps.now_kst) but the API must still
    report the real UTC instant -- a sign error or forgotten conversion in
    the KST->UTC serializer would silently shift every timestamp by +-9h
    while still matching the ISO8601 regex, so assert the actual value."""
    email = f"dt-{uuid.uuid4().hex}@example.com"
    before = datetime.now(UTC)

    resp = client.post("/api/v1/auth/signup", json={"email": email, "password": "Example123!"})

    after = datetime.now(UTC)
    created_at = datetime.strptime(resp.json()["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=UTC
    )
    assert before - timedelta(seconds=5) <= created_at <= after + timedelta(seconds=5), (
        f"created_at {created_at} is not close to real UTC now ({before} ~ {after}) -- "
        "looks like a KST/UTC offset bug"
    )


def test_profile_timestamps_are_utc_iso8601(client, signup_and_login):
    headers, _ = signup_and_login()

    body = client.get("/api/v1/users/me", headers=headers).json()

    for field in ("created_at", "updated_at"):
        assert ISO8601_UTC.match(body[field]), f"{field} not ISO8601 UTC: {body[field]!r}"


def test_login_user_timestamps_are_utc_iso8601(client, signup_and_login):
    email = f"dt-{uuid.uuid4().hex}@example.com"
    password = "Example123!"
    client.post("/api/v1/auth/signup", json={"email": email, "password": password})

    body = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()

    for field in ("created_at", "updated_at"):
        assert ISO8601_UTC.match(body["user"][field])


def test_favorite_created_at_is_utc_iso8601(client, signup_and_login):
    headers, _ = signup_and_login()
    client.post("/api/v1/favorites", json={"class_id": 6}, headers=headers)

    body = client.get("/api/v1/favorites", headers=headers).json()

    assert body["items"], "expected the favorite just created"
    assert ISO8601_UTC.match(body["items"][0]["created_at"])
