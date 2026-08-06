"""Shared pytest fixtures.

Uses a single in-memory SQLite engine (StaticPool so the DB is process-wide)
and drops/recreates schema between tests for isolation.
"""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-please-change")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "test-encryption-secret-value-please-change")

import pytest  # noqa: E402


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from sqlmodel import SQLModel
    from app import models  # noqa: F401  # ensures models are registered
    from app.db.session import engine
    from app.main import app

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(client):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "correcthorse-battery"
    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Test User",
        "workspace_name": "Test Workspace",
    })
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
