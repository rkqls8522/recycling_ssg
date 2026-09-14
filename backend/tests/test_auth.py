from __future__ import annotations


def test_signup_success(client):
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "new_user@example.com", "password": "Example123!"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new_user@example.com"
    assert body["region"] is None
    assert "user_id" in body


def test_signup_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "Example123!"}
    first = client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409
    assert second.json()["code"] == "AUTH_EMAIL_EXISTS"


def test_signup_validation_error(client):
    resp = client.post("/api/v1/auth/signup", json={"email": "not-an-email", "password": "short"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "REQUEST_VALIDATION_ERROR"
    assert isinstance(resp.json()["details"], list)


def test_login_success_and_invalid_credentials(client):
    payload = {"email": "login_test@example.com", "password": "Example123!"}
    client.post("/api/v1/auth/signup", json=payload)

    ok = client.post("/api/v1/auth/login", json=payload)
    assert ok.status_code == 200
    body = ok.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": payload["email"], "password": "WrongPass1!"}
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["code"] == "AUTH_INVALID_CREDENTIALS"

    unknown_email = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Example123!"}
    )
    assert unknown_email.status_code == 401


def test_logout_requires_auth_then_succeeds(client, signup_and_login):
    no_auth = client.post("/api/v1/auth/logout")
    assert no_auth.status_code == 401
    assert no_auth.json()["code"] == "AUTH_REQUIRED"

    headers, _ = signup_and_login()
    resp = client.post("/api/v1/auth/logout", headers=headers)
    assert resp.status_code == 204


def test_request_id_echoed_on_every_response(client):
    resp = client.get("/health", headers={"X-Request-ID": "my-custom-id"})
    assert resp.headers["X-Request-ID"] == "my-custom-id"

    resp2 = client.get("/health")
    assert "X-Request-ID" in resp2.headers
