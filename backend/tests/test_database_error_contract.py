"""A database failure must always surface as 503 DATABASE_ERROR, never 500.

Regression test: the signup duplicate-email lookup ran before the endpoint's
try/except, so a DB outage leaked a 500 INTERNAL_SERVER_ERROR even though
every endpoint's 오류 표 in the spec lists 503 DATABASE_ERROR.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Query, Session


def _boom(*args, **kwargs):
    raise OperationalError("SELECT 1", {}, Exception("connection refused"))


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/api/v1/auth/signup", {"email": "db@example.com", "password": "Example123!"}),
        ("POST", "/api/v1/auth/login", {"email": "db@example.com", "password": "Example123!"}),
    ],
)
def test_public_endpoints_report_503_when_db_is_down(client, monkeypatch, method, path, payload):
    monkeypatch.setattr(Query, "first", _boom)

    resp = client.request(method, path, json=payload)

    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["code"] == "DATABASE_ERROR"
    assert body["message"] == "데이터베이스 처리 중 오류가 발생했습니다."
    assert body["request_id"] == resp.headers["X-Request-ID"]


def test_authenticated_endpoint_reports_503_when_db_is_down(client, signup_and_login, monkeypatch):
    headers, _ = signup_and_login()
    monkeypatch.setattr(Session, "get", _boom)

    resp = client.get("/api/v1/users/me", headers=headers)

    assert resp.status_code == 503
    assert resp.json()["code"] == "DATABASE_ERROR"


def test_regions_reports_503_when_db_is_down(client, monkeypatch):
    monkeypatch.setattr(Query, "all", _boom)

    resp = client.get("/api/v1/regions")

    assert resp.status_code == 503
    assert resp.json()["code"] == "DATABASE_ERROR"


def test_signup_still_returns_409_for_real_duplicates(client):
    """The new guard must not swallow the duplicate-email path."""
    email = f"dup-{uuid.uuid4().hex}@example.com"
    payload = {"email": email, "password": "Example123!"}

    assert client.post("/api/v1/auth/signup", json=payload).status_code == 201

    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 409
    assert resp.json()["code"] == "AUTH_EMAIL_EXISTS"
