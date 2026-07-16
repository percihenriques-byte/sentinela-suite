"""Tests for week_summary intent + proactive nudges in /jarvis/context."""
from datetime import datetime, timedelta, timezone


def _iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def _chat(client, message):
    resp = client.post("/api/v1/jarvis/chat", json={"message": message})
    assert resp.status_code == 200
    return resp.json()


def test_week_summary_intent(auth_client):
    now = datetime.now(timezone.utc)
    # Opportunity closing tomorrow.
    auth_client.post("/api/v1/opportunities", json={
        "name": "Closing soon", "amount": 1000,
        "expected_close_date": _iso(now + timedelta(days=1)),
    })
    body = _chat(auth_client, "this week")
    assert body["intent"] == "week_summary"
    assert body["fallback"] is False


def test_nudges_include_hot_lead(auth_client):
    auth_client.post("/api/v1/leads", json={
        "first_name": "Hot", "last_name": "Prospect", "score": 90,
    })
    ctx = auth_client.get("/api/v1/jarvis/context").json()
    assert isinstance(ctx["nudges"], list)
    assert any("Hot" in n["message"] or "hot" in n["message"].lower() for n in ctx["nudges"])


def test_nudges_flag_many_overdue_tasks(auth_client):
    past = datetime.now(timezone.utc) - timedelta(days=2)
    for i in range(4):
        auth_client.post("/api/v1/tasks", json={
            "title": f"Old task {i}", "due_at": _iso(past),
        })
    ctx = auth_client.get("/api/v1/jarvis/context").json()
    assert any(n["level"] == "warn" and "overdue" in n["message"] for n in ctx["nudges"])
