"""Smoke tests — verify imports and that the app can start."""


def test_models_import():
    from app import models
    assert models.User is not None
    assert models.Workspace is not None
    assert models.Contact is not None
    assert models.Opportunity is not None


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_and_login(client):
    resp = client.post("/api/v1/auth/register", json={
        "email": "founder@example.com",
        "password": "correcthorse-battery",
        "full_name": "Founder One",
        "workspace_name": "Acme Co",
    })
    assert resp.status_code == 201, resp.text
    tokens = resp.json()
    assert "access_token" in tokens

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "founder@example.com"

    login = client.post("/api/v1/auth/login", json={
        "email": "founder@example.com",
        "password": "correcthorse-battery",
    })
    assert login.status_code == 200
    assert "access_token" in login.json()
