"""TEMP audit probe for the cross-cutting error catalog. Delete after run."""
from __future__ import annotations

import json

from fastapi import APIRouter


def _dump(label, resp):
    try:
        body = json.dumps(resp.json(), ensure_ascii=False)
    except Exception:
        body = repr(resp.text)[:300]
    print(
        f"[{label}] status={resp.status_code} xrid={resp.headers.get('X-Request-ID')!r} body={body}"
    )


def test_probe_unknown_route_and_method(client):
    _dump("404-unknown-route", client.get("/api/v1/nope"))
    _dump("405-wrong-method", client.get("/api/v1/auth/login"))
    _dump("health-success", client.get("/health"))
    _dump("422-validation", client.post("/api/v1/auth/signup", json={"email": "x"}))
    _dump("401-no-auth", client.get("/api/v1/users/me"))
    _dump("401-bad-scheme", client.get("/api/v1/users/me", headers={"Authorization": "Token abc"}))
    _dump("401-bad-token", client.get("/api/v1/users/me", headers={"Authorization": "Bearer abc"}))
    r = client.get("/health", headers={"X-Request-ID": "client-supplied-id"})
    _dump("health-echo-rid", r)


def test_probe_unhandled_exception(client):
    from main import app

    router = APIRouter()

    @router.get("/__boom__")
    def boom():
        raise RuntimeError("boom")

    app.include_router(router)
    app.router.routes  # noqa: B018
    try:
        resp = client.get("/__boom__")
        _dump("500-unhandled", resp)
    except Exception as exc:  # TestClient re-raises by default
        print("[500-unhandled] TestClient raised:", type(exc).__name__, exc)

    c2 = client.__class__(app, raise_server_exceptions=False)
    resp2 = c2.get("/__boom__")
    _dump("500-unhandled-noraise", resp2)


def test_probe_options_preflight(client):
    resp = client.options(
        "/api/v1/users/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    _dump("options-preflight", resp)


def test_probe_regions_validation(client, signup_and_login):
    headers, _ = signup_and_login()
    _dump("regions-bad-sido", client.get("/api/v1/regions", params={"sido_name": "부산"}, headers=headers))
    _dump("favorites-bad-path", client.delete("/api/v1/favorites/abc", headers=headers))
    _dump("feedback-path-zero", client.post("/api/v1/feedback/0/confirm", headers=headers))
