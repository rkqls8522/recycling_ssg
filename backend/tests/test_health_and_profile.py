"""GET /health, GET /ready (섹션 14) and GET /api/v1/users/me (섹션 7.1)."""

from __future__ import annotations

from core import database


def test_health_is_public_and_returns_service_identity(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "backend"}


def test_ready_reports_database_connectivity(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ready", "database": True}


def test_ready_returns_503_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(database, "check_db_connection", lambda: False)
    # api.health imports the function by name, so patch it there too.
    from api import health as health_api

    monkeypatch.setattr(health_api, "check_db_connection", lambda: False)

    resp = client.get("/ready")

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "SERVICE_NOT_READY"
    assert body["message"] == "서비스 준비가 완료되지 않았습니다."


def test_users_me_returns_profile_with_null_region_before_selection(client, signup_and_login):
    headers, user_id = signup_and_login()

    resp = client.get("/api/v1/users/me", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"user_id", "email", "region", "created_at", "updated_at"}
    assert body["user_id"] == user_id
    assert body["region"] is None  # Nullable=Yes until the user picks one
    assert "password" not in body and "password_hash" not in body


def test_users_me_includes_region_after_selection(client, signup_and_login):
    headers, _ = signup_and_login()
    client.patch("/api/v1/users/me/region", json={"region_id": 38}, headers=headers)

    resp = client.get("/api/v1/users/me", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["region"] == {
        "region_id": 38,
        "sido_name": "경기도",
        "sgg_name": "수원시",
    }


def test_users_me_rejects_bad_tokens(client):
    assert client.get("/api/v1/users/me").json()["code"] == "AUTH_REQUIRED"

    garbage = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert garbage.status_code == 401
    assert garbage.json()["code"] == "AUTH_TOKEN_INVALID"

    wrong_scheme = client.get("/api/v1/users/me", headers={"Authorization": "Basic abc"})
    assert wrong_scheme.status_code == 401
    assert wrong_scheme.json()["code"] == "AUTH_TOKEN_INVALID"


def test_users_me_rejects_expired_token(client, signup_and_login, monkeypatch):
    from core import security

    _, user_id = signup_and_login()

    # Issue a token that already expired an hour ago.
    monkeypatch.setattr(security.settings, "jwt_access_token_expire_minutes", -60)
    expired_token = security.create_access_token(user_id)
    monkeypatch.undo()

    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "AUTH_TOKEN_EXPIRED"
    assert body["message"] == "로그인이 만료되었습니다. 다시 로그인해주세요."
