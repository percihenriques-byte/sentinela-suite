"""Tests for Task/Meeting/Note endpoints + Jarvis context fallback."""
from datetime import datetime, timedelta, timezone


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def test_task_lifecycle(auth_client):
    client = auth_client
    due = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post("/api/v1/tasks", json={
        "title": "Call Jane",
        "priority": "high",
        "due_at": _iso(due),
    })
    assert resp.status_code == 201, resp.text
    task = resp.json()
    assert task["priority"] == "high"
    assert task["status"] == "todo"

    resp = client.get("/api/v1/tasks")
    body = resp.json()
    assert body["total"] == 1

    resp = client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "done"})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "done"
    assert updated["completed_at"] is not None

    resp = client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "bogus"})
    assert resp.status_code == 400


def test_meeting_window_validation(auth_client):
    client = auth_client
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start - timedelta(minutes=15)
    resp = client.post("/api/v1/meetings", json={
        "title": "Bad meeting",
        "starts_at": _iso(start),
        "ends_at": _iso(end),
    })
    assert resp.status_code == 400


def test_meeting_crud_and_filter(auth_client):
    client = auth_client
    now = datetime.now(timezone.utc)
    m1 = client.post("/api/v1/meetings", json={
        "title": "Kickoff",
        "starts_at": _iso(now + timedelta(hours=1)),
        "ends_at": _iso(now + timedelta(hours=2)),
    }).json()
    m2 = client.post("/api/v1/meetings", json={
        "title": "Follow-up",
        "starts_at": _iso(now + timedelta(days=3)),
        "ends_at": _iso(now + timedelta(days=3, hours=1)),
    }).json()

    # Window filter should include only m1
    resp = client.get(
        "/api/v1/meetings",
        params={"since": _iso(now), "until": _iso(now + timedelta(days=1))},
    )
    body = resp.json()
    ids = [m["id"] for m in body["items"]]
    assert m1["id"] in ids
    assert m2["id"] not in ids


def test_note_related_filter(auth_client):
    client = auth_client
    company = client.post("/api/v1/companies", json={"name": "N Corp"}).json()
    contact = client.post("/api/v1/contacts", json={
        "first_name": "Nora",
        "company_id": company["id"],
    }).json()

    client.post("/api/v1/notes", json={"body": "General note"})
    client.post("/api/v1/notes", json={"body": "About Nora", "related_contact_id": contact["id"]})

    resp = client.get(f"/api/v1/notes?contact_id={contact['id']}")
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["body"] == "About Nora"


def test_jarvis_context_endpoint(auth_client):
    client = auth_client
    client.post("/api/v1/companies", json={"name": "Ctx Co"})
    resp = client.get("/api/v1/jarvis/context")
    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"]["companies"] >= 1
    assert "generated_at" in body


def test_jarvis_chat_greets_locally_without_key(auth_client):
    """No cloud API key — the local engine still handles greetings."""
    client = auth_client
    resp = client.post("/api/v1/jarvis/chat", json={"message": "Hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["fallback"] is False, body
    assert "Jarvis" in body["reply"]


def test_jarvis_chat_local_summarize_pipeline(auth_client):
    client = auth_client
    client.post("/api/v1/opportunities", json={"name": "Deal A", "amount": 1000})
    client.post("/api/v1/opportunities", json={"name": "Deal B", "amount": 5000})
    resp = client.post("/api/v1/jarvis/chat", json={"message": "summarize pipeline"})
    body = resp.json()
    assert body["fallback"] is False
    assert "Pipeline" in body["reply"]
    assert any(tc["name"] == "summarize_pipeline" for tc in body["tool_calls"])


def test_jarvis_chat_local_create_task(auth_client):
    client = auth_client
    resp = client.post("/api/v1/jarvis/chat", json={"message": "create task: call John tomorrow"})
    body = resp.json()
    assert body["fallback"] is False
    assert "Task created" in body["reply"] or "call John" in body["reply"]

    # Verify a task actually exists now.
    tasks = client.get("/api/v1/tasks").json()
    assert tasks["total"] == 1
    assert "call John" in tasks["items"][0]["title"]


def test_jarvis_chat_unknown_escalates_gracefully_without_key(auth_client):
    """Unknown intent + no API key → helpful hint, not a 500."""
    client = auth_client
    resp = client.post("/api/v1/jarvis/chat", json={"message": "please write a haiku about SaaS"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["fallback"] is True
    assert "help" in body["reply"].lower() or "ajuda" in body["reply"].lower()
