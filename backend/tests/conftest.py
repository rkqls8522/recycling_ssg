"""Pytest fixtures.

Uses a temp-file SQLite DB instead of MySQL so the suite runs without any
external services. All environment variables must be set *before* any
``core.*``/``main`` module is imported, since ``core.config.settings`` is a
module-level singleton read once at import time.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

_db_fd, _db_path = tempfile.mkstemp(suffix=".sqlite3")
os.close(_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["AUTO_SEED_MASTER_DATA"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["AWS_S3_BUCKET"] = "test-bucket"
os.environ.setdefault("GEMINI_API_KEY", "")

import pytest
from fastapi.testclient import TestClient

import models  # noqa: F401 - populates Base.metadata
from core.database import Base, SessionLocal, engine
from db.seed import seed_all
from main import app


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    yield
    engine.dispose()
    Path(_db_path).unlink(missing_ok=True)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def signup_and_login(client: TestClient):
    """Returns a factory that signs up + logs in a fresh user, returning
    (headers, user_id). Uses a UUID per call so emails stay unique across
    the whole (shared, file-backed) test database, not just within one
    test function."""

    def _make():
        email = f"user-{uuid.uuid4().hex}@example.com"
        password = "Example123!"

        signup_resp = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
        assert signup_resp.status_code == 201, signup_resp.text

        login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login_resp.status_code == 200, login_resp.text
        body = login_resp.json()
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        return headers, body["user"]["user_id"]

    return _make
