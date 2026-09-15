"""Cross-cutting checks from the 구현 체크리스트 (섹션 20):

* every response — success *and* error — carries an X-Request-ID header
* every HTTP error body has success/code/message/details/request_id
* a client-supplied X-Request-ID is echoed back and reused in error bodies
* the router exposes exactly the 17 backend endpoints of 섹션 5 with the
  documented auth requirement
"""

from __future__ import annotations

import pytest

from main import app

# (method, path, needs_auth) exactly as listed in 섹션 5.
EXPECTED_ROUTES = {
    ("GET", "/health", False),
    ("GET", "/ready", False),
    ("POST", "/api/v1/auth/signup", False),
    ("POST", "/api/v1/auth/login", False),
    ("POST", "/api/v1/auth/logout", True),
    ("GET", "/api/v1/users/me", True),
    ("GET", "/api/v1/regions", False),
    ("PATCH", "/api/v1/users/me/region", True),
    ("POST", "/api/v1/analyze", True),
    ("POST", "/api/v1/feedback/{feedback_id}/confirm", True),
    ("POST", "/api/v1/feedback/{feedback_id}/select-candidate", True),
    ("POST", "/api/v1/feedback/{feedback_id}/not-in-list", True),
    ("GET", "/api/v1/disposal/schedule", True),
    ("POST", "/api/v1/chat", True),
    ("GET", "/api/v1/favorites", True),
    ("POST", "/api/v1/favorites", True),
    ("DELETE", "/api/v1/favorites/{favorite_id}", True),
}


def _registered_routes() -> set[tuple[str, str]]:
    """Enumerates the public API surface from the generated OpenAPI schema.
    (Included routers are nested objects on ``app.routes`` in this FastAPI
    version, so the schema is both simpler and closer to what clients see.)"""
    schema = app.openapi()
    return {
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        for method in operations
        if method.upper() not in {"HEAD", "OPTIONS"}
    }


def test_all_17_backend_endpoints_are_registered():
    registered = _registered_routes()
    expected = {(m, p) for m, p, _ in EXPECTED_ROUTES}

    assert expected <= registered, f"missing routes: {expected - registered}"
    assert len(expected) == 17
    # No undocumented extra API surface.
    assert registered - expected == set(), f"unexpected routes: {registered - expected}"


@pytest.mark.parametrize(
    ("method", "path"),
    sorted({(m, p) for m, p, needs_auth in EXPECTED_ROUTES if needs_auth}),
)
def test_protected_endpoints_reject_anonymous_requests(client, method, path):
    concrete = path.replace("{feedback_id}", "1").replace("{favorite_id}", "1")

    resp = client.request(method, concrete)

    assert resp.status_code == 401, f"{method} {concrete} should require auth"
    body = resp.json()
    assert body["code"] == "AUTH_REQUIRED"
    assert body["message"] == "로그인이 필요합니다."


@pytest.mark.parametrize(
    ("method", "path"),
    sorted({(m, p) for m, p, needs_auth in EXPECTED_ROUTES if not needs_auth}),
)
def test_public_endpoints_do_not_require_auth(client, method, path):
    resp = client.request(method, path, json={} if method == "POST" else None)
    assert resp.status_code != 401


def test_error_body_has_all_five_contract_fields(client):
    resp = client.get("/api/v1/users/me")  # 401 AUTH_REQUIRED

    assert resp.status_code == 401
    body = resp.json()
    assert set(body) == {"success", "code", "message", "details", "request_id"}
    assert body["success"] is False
    assert isinstance(body["code"], str) and body["code"]
    assert isinstance(body["message"], str) and body["message"]
    assert body["details"] is None  # Nullable=Yes -> explicit null, key still present
    assert body["request_id"] == resp.headers["X-Request-ID"]


def test_validation_error_details_use_field_message_shape(client):
    resp = client.post("/api/v1/auth/signup", json={"email": "not-an-email"})

    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "REQUEST_VALIDATION_ERROR"
    assert body["message"] == "요청 값이 올바르지 않습니다."
    assert isinstance(body["details"], list) and body["details"]
    for detail in body["details"]:
        assert set(detail) == {"field", "message"}  # 섹션 16.1
    assert {d["field"] for d in body["details"]} >= {"email", "password"}


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("GET", "/health", {}),
        ("GET", "/ready", {}),
        ("GET", "/api/v1/users/me", {}),  # error path
        ("POST", "/api/v1/auth/signup", {"json": {"email": "x", "password": "y"}}),
        ("GET", "/nonexistent-route", {}),  # 404 from the framework
    ],
)
def test_request_id_header_present_on_every_response(client, method, path, kwargs):
    resp = client.request(method, path, **kwargs)
    assert resp.headers.get("X-Request-ID"), f"{method} {path} missing X-Request-ID"


def test_client_supplied_request_id_is_echoed_and_reused_in_error_body(client):
    supplied = "550e8400-e29b-41d4-a716-446655440000"

    resp = client.get("/api/v1/users/me", headers={"X-Request-ID": supplied})

    assert resp.headers["X-Request-ID"] == supplied
    assert resp.json()["request_id"] == supplied


def test_unknown_route_returns_contract_shaped_error(client):
    resp = client.get("/api/v1/does-not-exist")

    assert resp.status_code == 404
    body = resp.json()
    assert set(body) == {"success", "code", "message", "details", "request_id"}
    assert body["success"] is False
