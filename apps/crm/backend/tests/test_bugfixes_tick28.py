"""Regression tests for the tick-28 review pass — live-server probes."""


def test_won_stage_move_snaps_probability_to_100(auth_client):
    """Before fix: PATCHing an opp into 'Won' left probability at whatever
    the previous stage was (e.g. 10% from Prospecting) — losses of thousands
    of $ in weighted-pipeline math."""
    opp = auth_client.post("/api/v1/opportunities", json={
        "name": "Test", "amount": 1000,
    }).json()
    assert opp["probability"] == 10.0  # Prospecting default

    p = auth_client.get("/api/v1/pipelines").json()[0]
    won = next(s for s in p["stages"] if s["name"] == "Won")
    r = auth_client.patch(f"/api/v1/opportunities/{opp['id']}",
                          json={"stage_id": won["id"]}).json()
    assert r["status"] == "won"
    assert r["probability"] == 100.0, r
    assert r["closed_at"] is not None


def test_lost_stage_move_snaps_probability_to_0(auth_client):
    opp = auth_client.post("/api/v1/opportunities", json={
        "name": "Fizzle", "amount": 500,
    }).json()
    p = auth_client.get("/api/v1/pipelines").json()[0]
    lost = next(s for s in p["stages"] if s["name"] == "Lost")
    r = auth_client.patch(f"/api/v1/opportunities/{opp['id']}",
                          json={"stage_id": lost["id"]}).json()
    assert r["status"] == "lost"
    assert r["probability"] == 0.0
    assert r["closed_at"] is not None


def test_explicit_probability_overrides_stage_default(auth_client):
    """Caller-supplied probability wins — the fix uses `setdefault`."""
    opp = auth_client.post("/api/v1/opportunities", json={
        "name": "Custom", "amount": 500,
    }).json()
    p = auth_client.get("/api/v1/pipelines").json()[0]
    won = next(s for s in p["stages"] if s["name"] == "Won")
    r = auth_client.patch(f"/api/v1/opportunities/{opp['id']}",
                          json={"stage_id": won["id"], "probability": 85}).json()
    assert r["status"] == "won"
    assert r["probability"] == 85.0


def test_workflow_template_substitution_end_to_end(auth_client):
    """Live-server probe: workflow that creates a task with
    `Follow up with {{subject_id}}` renders the lead's UUID."""
    auth_client.post("/api/v1/workflows", json={
        "name": "high-score",
        "trigger": {
            "kind": "created", "subject_type": "lead",
            "conditions": [{"field": "subject.score", "op": "gte", "value": "50"}],
        },
        "steps": [{"kind": "create_task", "payload": {
            "title": "Follow up with {{subject_id}}",
            "due_in_days": 2, "priority": "high",
        }}],
    })
    lead = auth_client.post("/api/v1/leads", json={"first_name": "H", "score": 75}).json()
    tasks = auth_client.get("/api/v1/tasks").json()
    auto = next((t for t in tasks["items"] if "Follow up" in t["title"]), None)
    assert auto is not None
    # Template rendered the actual lead id, not the literal `{{subject_id}}`
    assert lead["id"] in auto["title"], auto["title"]
    assert auto["priority"] == "high"
    assert auto["related_lead_id"] == lead["id"]
