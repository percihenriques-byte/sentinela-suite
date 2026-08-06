"""Tests for demo seed endpoint + workflow model registration."""


def test_seed_demo_populates_workspace(auth_client):
    resp = auth_client.post("/api/v1/workspaces/current/seed-demo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    counts = body["counts"]
    assert counts["companies"] >= 5
    assert counts["contacts"] >= 8
    assert counts["opportunities"] >= 5

    # Verify entities are readable via API.
    companies = auth_client.get("/api/v1/companies").json()
    assert companies["total"] >= 5
    opps = auth_client.get("/api/v1/opportunities").json()
    assert opps["total"] >= 5

    # Second seed on a non-empty workspace should skip.
    resp = auth_client.post("/api/v1/workspaces/current/seed-demo")
    body = resp.json()
    assert body["status"] == "skipped"


def test_seed_demo_force(auth_client):
    auth_client.post("/api/v1/workspaces/current/seed-demo")
    resp = auth_client.post("/api/v1/workspaces/current/seed-demo?force=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_workflow_models_registered():
    from app import models
    assert models.Workflow is not None
    assert models.WorkflowStep is not None
    assert models.WorkflowRun is not None
