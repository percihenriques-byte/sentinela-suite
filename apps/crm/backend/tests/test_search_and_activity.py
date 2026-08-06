"""Tests for search_everywhere intent + subject-scoped activity endpoint."""


def _chat(client, message):
    resp = client.post("/api/v1/jarvis/chat", json={"message": message})
    assert resp.status_code == 200
    return resp.json()


def test_search_everywhere_matches_across_kinds(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "Nebula Labs", "industry": "AI"})
    auth_client.post("/api/v1/contacts", json={"first_name": "Nebula", "last_name": "Neighbor"})
    auth_client.post("/api/v1/opportunities", json={"name": "Nebula onboarding", "amount": 500})
    auth_client.post("/api/v1/notes", json={"body": "Talked to Nebula about pricing"})

    body = _chat(auth_client, "search everywhere for Nebula")
    assert body["fallback"] is False, body
    assert body["intent"] == "search_everywhere"
    tool = next(tc for tc in body["tool_calls"] if tc["name"] == "search_everywhere")
    r = tool["result"]["results"]
    assert len(r["contacts"]) == 1
    assert len(r["companies"]) == 1
    assert len(r["opportunities"]) == 1
    assert len(r["notes"]) == 1
    assert tool["result"]["total"] >= 4


def test_search_everywhere_no_match(auth_client):
    body = _chat(auth_client, "search everywhere for zzzzz")
    assert body["intent"] == "search_everywhere"
    assert "Nothing" in body["reply"] or "Nada" in body["reply"]


def test_activity_endpoint_filters_by_subject(auth_client):
    company = auth_client.post("/api/v1/companies", json={"name": "Timeline Corp"}).json()
    contact = auth_client.post("/api/v1/contacts", json={"first_name": "T"}).json()

    # Every CRUD write logs an Activity — so we have at least 2 rows now.
    resp = auth_client.get(f"/api/v1/activities?subject_type=company&subject_id={company['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for row in body["items"]:
        assert row["subject_type"] == "company"
        assert row["subject_id"] == company["id"]

    # Contact activity is separate.
    resp = auth_client.get(f"/api/v1/activities?subject_type=contact&subject_id={contact['id']}")
    body = resp.json()
    assert body["total"] >= 1
    for row in body["items"]:
        assert row["subject_type"] == "contact"


def test_activity_endpoint_unfiltered_returns_all(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "A"})
    auth_client.post("/api/v1/companies", json={"name": "B"})
    resp = auth_client.get("/api/v1/activities")
    body = resp.json()
    assert body["total"] >= 2
