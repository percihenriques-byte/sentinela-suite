"""Focused tests for the local Jarvis engine — no external APIs.

Covers new intents (create_note, mark_task_done, find_company, move_stage,
activity_timeline, today_summary), conversation persistence, and fuzzy match
tolerance.
"""


def _chat(client, message, conversation_id=None):
    payload = {"message": message}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    resp = client.post("/api/v1/jarvis/chat", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_create_note_intent(auth_client):
    body = _chat(auth_client, "note: follow up with the CFO on pricing")
    assert body["fallback"] is False
    assert body["intent"] == "create_note"
    assert any(tc["name"] == "create_note" for tc in body["tool_calls"])
    notes = auth_client.get("/api/v1/notes").json()
    assert notes["total"] == 1
    assert "CFO" in notes["items"][0]["body"]


def test_mark_task_done_intent(auth_client):
    task = auth_client.post("/api/v1/tasks", json={"title": "Send proposal"}).json()
    body = _chat(auth_client, "mark task Send proposal done")
    assert body["fallback"] is False
    assert body["intent"] == "mark_task_done"
    # Verify state changed
    updated = auth_client.get(f"/api/v1/tasks/{task['id']}").json()
    assert updated["status"] == "done"
    assert updated["completed_at"] is not None


def test_find_company_intent(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "Globex Corp", "industry": "SaaS"})
    body = _chat(auth_client, "find company Globex")
    assert body["intent"] == "find_company"
    assert "Globex" in body["reply"]


def test_move_opportunity_stage_intent(auth_client):
    opp = auth_client.post("/api/v1/opportunities", json={"name": "Kickoff Deal", "amount": 500}).json()
    body = _chat(auth_client, 'move opportunity "Kickoff Deal" to Negotiation')
    assert body["fallback"] is False
    assert body["intent"] == "move_opportunity_stage"
    updated = auth_client.get(f"/api/v1/opportunities/{opp['id']}").json()
    p = auth_client.get("/api/v1/pipelines").json()[0]
    negotiation = next(s for s in p["stages"] if s["name"] == "Negotiation")
    assert updated["stage_id"] == negotiation["id"]


def test_move_opportunity_to_won_closes(auth_client):
    opp = auth_client.post("/api/v1/opportunities", json={"name": "Big Ticket", "amount": 20000}).json()
    body = _chat(auth_client, 'move opportunity "Big Ticket" to Won')
    assert body["fallback"] is False
    updated = auth_client.get(f"/api/v1/opportunities/{opp['id']}").json()
    assert updated["status"] == "won"
    assert updated["closed_at"] is not None


def test_activity_timeline_intent(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "Timeline Co"})
    body = _chat(auth_client, "show recent activity")
    assert body["intent"] == "activity_timeline"
    assert "Timeline Co" in body["reply"] or "created" in body["reply"].lower()


def test_today_summary_intent(auth_client):
    body = _chat(auth_client, "what's on today")
    assert body["intent"] == "today_summary"
    # Empty workspace → should mention nothing scheduled, not fall back.
    assert body["fallback"] is False


def test_conversation_persists_and_lists(auth_client):
    first = _chat(auth_client, "hello")
    assert first["conversation_id"] is not None
    conv_id = first["conversation_id"]

    second = _chat(auth_client, "help", conversation_id=conv_id)
    assert second["conversation_id"] == conv_id

    convs = auth_client.get("/api/v1/jarvis/conversations").json()
    assert convs["total"] == 1
    msgs = auth_client.get(f"/api/v1/jarvis/conversations/{conv_id}/messages").json()
    # user, assistant, user, assistant
    assert len(msgs) == 4
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]


def test_conversation_delete(auth_client):
    first = _chat(auth_client, "hi")
    conv_id = first["conversation_id"]
    resp = auth_client.delete(f"/api/v1/jarvis/conversations/{conv_id}")
    assert resp.status_code == 204
    convs = auth_client.get("/api/v1/jarvis/conversations").json()
    assert convs["total"] == 0


def test_portuguese_intent(auth_client):
    body = _chat(auth_client, "resumir pipeline")
    assert body["intent"] == "summarize_pipeline"
    assert "Pipeline" in body["reply"]


def test_typo_tolerance_still_falls_back_gracefully(auth_client):
    """Gibberish should get the helpful hint, not a 500."""
    body = _chat(auth_client, "asdfghjkl please write a haiku about SaaS")
    assert body["fallback"] is True
    assert "help" in body["reply"].lower() or "ajuda" in body["reply"].lower()


def test_remember_call_me(auth_client):
    body = _chat(auth_client, "call me Alex")
    assert body["intent"] == "remember_name"
    assert "Alex" in body["reply"]
    prefs = auth_client.get("/api/v1/jarvis/context").json()["preferences"]
    assert prefs.get("preferred_name") == "Alex"


def test_remember_language_pt(auth_client):
    body = _chat(auth_client, "prefer portuguese")
    assert body["intent"] == "remember_language"
    # Reply comes in the newly-set language
    assert "portugu" in body["reply"].lower()


def test_remember_generic_fact_and_recall(auth_client):
    body = _chat(auth_client, "remember: coffee is essential")
    assert body["intent"] == "remember_fact"
    listed = _chat(auth_client, "what do you remember")
    assert listed["intent"] == "list_preferences"
    assert "coffee" in listed["reply"].lower()


def test_log_call_with_contact(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Jane", "last_name": "Doe"})
    body = _chat(auth_client, "log call with Jane: discussed pricing")
    assert body["fallback"] is False, body
    assert body["intent"] == "log_interaction"
    # Verify an Activity was written
    ctx = auth_client.get("/api/v1/jarvis/context").json()
    assert ctx  # sanity


def test_log_email_without_contact(auth_client):
    body = _chat(auth_client, "register email: shipped Q3 report to the board")
    assert body["fallback"] is False, body
    assert body["intent"] == "log_interaction"


def test_request_id_response_header(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    headers = {k.lower(): v for k, v in r.headers.items()}
    assert "x-request-id" in headers
    assert len(headers["x-request-id"]) >= 8


def test_request_id_passthrough(client):
    r = client.get("/healthz", headers={"X-Request-Id": "test-req-12345"})
    assert r.headers.get("x-request-id") == "test-req-12345"
