"""Tests for lead scoring rules — evaluator + endpoints + Jarvis intent."""


def test_rule_applies_on_lead_create(auth_client):
    r = auth_client.post("/api/v1/lead-scoring/rules", json={
        "name": "Web source bonus", "field": "source", "op": "iequals", "value": "web", "score_delta": 10,
    })
    assert r.status_code == 201, r.text
    lead = auth_client.post("/api/v1/leads", json={
        "first_name": "Neo", "email": "neo@matrix.io", "source": "web",
    }).json()
    assert lead["score"] == 10, lead


def test_multiple_rules_additive(auth_client):
    auth_client.post("/api/v1/lead-scoring/rules", json={
        "name": "gmail domain", "field": "email_domain", "op": "iequals",
        "value": "gmail.com", "score_delta": 5,
    })
    auth_client.post("/api/v1/lead-scoring/rules", json={
        "name": "referral source", "field": "source", "op": "iequals",
        "value": "referral", "score_delta": 20,
    })
    lead = auth_client.post("/api/v1/leads", json={
        "first_name": "Amy", "email": "amy@gmail.com", "source": "referral",
    }).json()
    assert lead["score"] == 25


def test_regex_rule(auth_client):
    auth_client.post("/api/v1/lead-scoring/rules", json={
        "name": "enterprise-y company name", "field": "company_name", "op": "regex",
        "value": r"(corp|inc|ltd|s\.?a\.?)$", "score_delta": 15,
    })
    lead = auth_client.post("/api/v1/leads", json={
        "first_name": "Ent", "company_name": "MegaCorp Ltd",
    }).json()
    assert lead["score"] == 15


def test_recalculate_endpoint(auth_client):
    # Create a lead first with no rules; then add a rule and recalculate.
    lead = auth_client.post("/api/v1/leads", json={"first_name": "Later", "source": "cold-call"}).json()
    assert lead["score"] == 0
    auth_client.post("/api/v1/lead-scoring/rules", json={
        "name": "cold call", "field": "source", "op": "iequals", "value": "cold-call", "score_delta": 3,
    })
    r = auth_client.post("/api/v1/lead-scoring/recalculate")
    body = r.json()
    assert body["leads_updated"] == 1
    updated = auth_client.get(f"/api/v1/leads/{lead['id']}").json()
    assert updated["score"] == 3


def test_validation_rejects_unknown_field(auth_client):
    r = auth_client.post("/api/v1/lead-scoring/rules", json={
        "name": "bogus", "field": "not_a_field", "op": "iequals", "value": "x",
    })
    assert r.status_code == 400


def test_jarvis_recalculate_intent(auth_client):
    auth_client.post("/api/v1/lead-scoring/rules", json={
        "name": "any", "field": "source", "op": "is_present", "score_delta": 1,
    })
    auth_client.post("/api/v1/leads", json={"first_name": "S", "source": "seo"})
    resp = auth_client.post("/api/v1/jarvis/chat", json={"message": "recalculate lead scores"})
    body = resp.json()
    assert body["intent"] == "recalculate_lead_scores"
    assert body["fallback"] is False
