"""End-to-end tests for the workflow runtime."""


def test_lead_created_high_score_creates_task(auth_client):
    # Workflow: when a lead is created with score >= 50, create a follow-up task.
    wf = auth_client.post("/api/v1/workflows", json={
        "name": "High-value lead follow-up",
        "trigger": {
            "kind": "created",
            "subject_type": "lead",
            "conditions": [{"field": "subject.score", "op": "gte", "value": "50"}],
        },
        "steps": [
            {"kind": "create_task", "payload": {
                "title": "Follow up with high-value lead",
                "due_in_days": 2,
                "priority": "high",
            }}
        ],
    })
    assert wf.status_code == 201, wf.text
    wf_id = wf.json()["id"]

    # Below threshold — no task.
    auth_client.post("/api/v1/leads", json={"first_name": "Low", "score": 10})
    tasks = auth_client.get("/api/v1/tasks").json()
    assert tasks["total"] == 0

    # At/above threshold — one task created by the workflow.
    auth_client.post("/api/v1/leads", json={"first_name": "High", "score": 75})
    tasks = auth_client.get("/api/v1/tasks").json()
    assert tasks["total"] == 1
    assert "Follow up" in tasks["items"][0]["title"]
    assert tasks["items"][0]["priority"] == "high"

    # Workflow run recorded.
    runs = auth_client.get(f"/api/v1/workflows/{wf_id}/runs").json()
    assert len(runs) == 1
    assert runs[0]["status"] == "succeeded"


def test_workflow_add_note_on_company_created(auth_client):
    wf = auth_client.post("/api/v1/workflows", json={
        "name": "Welcome company",
        "trigger": {"kind": "created", "subject_type": "company"},
        "steps": [{"kind": "add_note", "payload": {"body": "Auto-onboarding note"}}],
    })
    assert wf.status_code == 201

    auth_client.post("/api/v1/companies", json={"name": "Nova"})
    notes = auth_client.get("/api/v1/notes").json()
    assert notes["total"] == 1
    assert "Auto-onboarding" in notes["items"][0]["body"]


def test_workflow_loop_guard_prevents_infinite_recursion(auth_client):
    """A workflow whose action itself logs an activity must not re-trigger itself."""
    auth_client.post("/api/v1/workflows", json={
        "name": "Add note to every note",
        "trigger": {"kind": "note_added"},
        "steps": [{"kind": "add_note", "payload": {"body": "Recursion trap"}}],
    })
    # If the loop guard were absent, this single note creation would recurse
    # indefinitely. With it, only the user's original note plus one workflow-
    # produced note should exist.
    auth_client.post("/api/v1/notes", json={"body": "Original"})
    notes = auth_client.get("/api/v1/notes").json()
    # Original + at most one workflow note. Never blows up.
    assert 1 <= notes["total"] <= 2


def test_workflow_disabled_does_not_run(auth_client):
    wf = auth_client.post("/api/v1/workflows", json={
        "name": "disabled",
        "is_active": False,
        "trigger": {"kind": "created", "subject_type": "company"},
        "steps": [{"kind": "add_note", "payload": {"body": "should not appear"}}],
    }).json()
    auth_client.post("/api/v1/companies", json={"name": "X"})
    notes = auth_client.get("/api/v1/notes").json()
    assert notes["total"] == 0


def test_workflow_unknown_step_kind_rejected(auth_client):
    r = auth_client.post("/api/v1/workflows", json={
        "name": "bad",
        "trigger": {"kind": "created"},
        "steps": [{"kind": "delete_universe", "payload": {}}],
    })
    assert r.status_code == 400
