"""Tests for the tick-6 additions: NL reschedule, forecast, contacts-by-company."""
from datetime import datetime, timedelta, timezone


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _chat(client, message, conversation_id=None):
    payload = {"message": message}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    resp = client.post("/api/v1/jarvis/chat", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_reschedule_meeting_natural_language(auth_client):
    now = datetime.now(timezone.utc)
    meeting = auth_client.post("/api/v1/meetings", json={
        "title": "Sync",
        "starts_at": _iso(now + timedelta(hours=2)),
        "ends_at": _iso(now + timedelta(hours=3)),
    }).json()
    body = _chat(auth_client, "reschedule Sync to tomorrow 3pm")
    assert body["fallback"] is False, body
    assert body["intent"] == "reschedule_meeting"
    updated = auth_client.get(f"/api/v1/meetings/{meeting['id']}").json()
    # Should now start tomorrow at 15:00 UTC (the parser assumes UTC).
    starts = datetime.fromisoformat(updated["starts_at"].replace("Z", "+00:00"))
    assert starts.hour == 15
    assert starts.date() == (now + timedelta(days=1)).date()


def test_forecast_bucketing(auth_client):
    now = datetime.now(timezone.utc)
    p = auth_client.get("/api/v1/pipelines").json()[0]
    prospecting = next(s for s in p["stages"] if s["name"] == "Prospecting")
    # this_week — must stay inside today's UTC calendar day AND before end_of_week.
    # end_of_week = 23:59:59 of Sunday. If the test runs after 22:00 UTC on Sunday,
    # `+2 hours` crosses midnight into Monday (next week) and the assertion fails.
    # Solution: clamp to a moment safely before 23:59 today.
    today_end = now.replace(hour=23, minute=45, second=0, microsecond=0)
    close_at = today_end if today_end > now else (now + timedelta(minutes=5))
    auth_client.post("/api/v1/opportunities", json={
        "name": "Deal A", "amount": 1000, "stage_id": prospecting["id"],
        "expected_close_date": _iso(close_at),
    })
    # overdue
    auth_client.post("/api/v1/opportunities", json={
        "name": "Deal B", "amount": 2000, "stage_id": prospecting["id"],
        "expected_close_date": _iso(now - timedelta(days=3)),
    })
    # no date
    auth_client.post("/api/v1/opportunities", json={
        "name": "Deal C", "amount": 3000, "stage_id": prospecting["id"],
    })
    body = _chat(auth_client, "forecast")
    assert body["intent"] == "forecast"
    forecast_call = next(tc for tc in body["tool_calls"] if tc["name"] == "forecast")
    buckets = forecast_call["result"]["buckets"]
    assert buckets["overdue"]["count"] == 1
    assert buckets["this_week"]["count"] == 1
    assert buckets["no_date"]["count"] == 1
    totals = forecast_call["result"]["totals"]
    assert totals["count"] == 3
    assert totals["amount"] == 6000.0


def test_who_works_at_intent(auth_client):
    company = auth_client.post("/api/v1/companies", json={"name": "Acme Ltd"}).json()
    auth_client.post("/api/v1/contacts", json={
        "first_name": "Ada", "last_name": "Byte", "company_id": company["id"], "job_title": "CTO",
    })
    auth_client.post("/api/v1/contacts", json={
        "first_name": "Grace", "last_name": "Hop", "company_id": company["id"],
    })
    # Contact not at Acme
    auth_client.post("/api/v1/contacts", json={"first_name": "Solo", "last_name": "Rogue"})

    body = _chat(auth_client, "who works at Acme")
    assert body["fallback"] is False, body
    assert body["intent"] == "list_contacts_by_company"
    assert "Ada" in body["reply"] and "Grace" in body["reply"]
    assert "Solo" not in body["reply"]


def test_who_works_at_unknown_company(auth_client):
    body = _chat(auth_client, "who works at Nonexistent Corp")
    assert body["intent"] == "list_contacts_by_company"
    assert "No company" in body["reply"] or "Não encontrei" in body["reply"]
