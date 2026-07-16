"""Verify fuzzy_keywords tolerate common typos on top intents."""


def _chat(client, message):
    resp = client.post("/api/v1/jarvis/chat", json={"message": message})
    assert resp.status_code == 200
    return resp.json()


def test_typo_in_summarize_pipeline(auth_client):
    body = _chat(auth_client, "sumarize the pipelne")
    # difflib cutoff 0.82 should tolerate one dropped char / swap
    assert body["intent"] == "summarize_pipeline", body


def test_typo_in_overdue_tasks(auth_client):
    body = _chat(auth_client, "overude taks")
    assert body["intent"] == "overdue_tasks", body


def test_typo_in_forecast(auth_client):
    body = _chat(auth_client, "forecaste")
    assert body["intent"] == "forecast", body


def test_typo_in_upcoming_meetings(auth_client):
    body = _chat(auth_client, "upcomming meetngs")
    assert body["intent"] == "upcoming_meetings", body


def test_still_falls_back_on_unrelated(auth_client):
    body = _chat(auth_client, "please write a haiku")
    assert body["fallback"] is True
