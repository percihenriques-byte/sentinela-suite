"""End-to-end tests for the CRM CRUD endpoints and lead conversion flow."""


def test_company_crud(auth_client):
    client = auth_client
    resp = client.post("/api/v1/companies", json={"name": "Acme", "domain": "acme.test"})
    assert resp.status_code == 201, resp.text
    company = resp.json()

    resp = client.get("/api/v1/companies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(c["id"] == company["id"] for c in body["items"])

    resp = client.patch(f"/api/v1/companies/{company['id']}", json={"industry": "SaaS"})
    assert resp.status_code == 200
    assert resp.json()["industry"] == "SaaS"

    resp = client.delete(f"/api/v1/companies/{company['id']}")
    assert resp.status_code == 204
    resp = client.get(f"/api/v1/companies/{company['id']}")
    assert resp.status_code == 404


def test_contact_requires_valid_company(auth_client):
    import uuid as _uuid
    client = auth_client
    fake = str(_uuid.uuid4())
    resp = client.post("/api/v1/contacts", json={
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "company_id": fake,
    })
    assert resp.status_code == 404


def test_contact_crud_with_company(auth_client):
    client = auth_client
    company = client.post("/api/v1/companies", json={"name": "Widgets Inc"}).json()

    resp = client.post("/api/v1/contacts", json={
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "company_id": company["id"],
    })
    assert resp.status_code == 201
    contact = resp.json()
    assert contact["company_id"] == company["id"]

    resp = client.get(f"/api/v1/contacts?company_id={company['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_pipeline_bootstrap(auth_client):
    client = auth_client
    resp = client.get("/api/v1/pipelines")
    assert resp.status_code == 200
    pipelines = resp.json()
    assert len(pipelines) == 1
    p = pipelines[0]
    assert p["is_default"] is True
    stage_names = [s["name"] for s in p["stages"]]
    assert stage_names == ["Prospecting", "Qualification", "Proposal", "Negotiation", "Won", "Lost"]


def test_opportunity_create_defaults_to_first_stage(auth_client):
    client = auth_client
    resp = client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 25000})
    assert resp.status_code == 201, resp.text
    opp = resp.json()
    assert opp["amount"] == 25000
    assert opp["status"] == "open"

    p = client.get("/api/v1/pipelines").json()[0]
    prospecting_stage = next(s for s in p["stages"] if s["name"] == "Prospecting")
    assert opp["stage_id"] == prospecting_stage["id"]


def test_opportunity_move_to_won_closes(auth_client):
    client = auth_client
    opp = client.post("/api/v1/opportunities", json={"name": "Deal X", "amount": 1000}).json()
    p = client.get("/api/v1/pipelines").json()[0]
    won_stage = next(s for s in p["stages"] if s["name"] == "Won")

    resp = client.patch(f"/api/v1/opportunities/{opp['id']}", json={"stage_id": won_stage["id"]})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "won"
    assert updated["closed_at"] is not None


def test_lead_conversion_creates_contact_and_opportunity(auth_client):
    client = auth_client
    lead = client.post("/api/v1/leads", json={
        "first_name": "John",
        "last_name": "Prospect",
        "email": "john@prospect.example.com",
        "company_name": "Prospect Corp",
    }).json()

    resp = client.post(f"/api/v1/leads/{lead['id']}/convert", json={
        "create_company": True,
        "create_opportunity": True,
        "amount": 5000,
        "currency": "USD",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["lead_id"] == lead["id"]
    assert body["contact_id"] is not None
    assert body["company_id"] is not None
    assert body["opportunity_id"] is not None

    # Lead should now be marked converted
    resp = client.get(f"/api/v1/leads/{lead['id']}")
    assert resp.json()["status"] == "converted"

    # Second conversion should fail
    resp = client.post(f"/api/v1/leads/{lead['id']}/convert", json={"create_opportunity": False})
    assert resp.status_code == 409


def test_workspace_isolation(client):
    """A user in workspace A must not see workspace B's data."""
    a = client.post("/api/v1/auth/register", json={
        "email": "alice@alice.example.com",
        "password": "correcthorse-battery",
        "full_name": "Alice",
        "workspace_name": "Alpha",
    }).json()
    b = client.post("/api/v1/auth/register", json={
        "email": "bob@bob.example.com",
        "password": "correcthorse-battery",
        "full_name": "Bob",
        "workspace_name": "Bravo",
    }).json()

    r = client.post(
        "/api/v1/companies",
        json={"name": "Alice Co"},
        headers={"Authorization": f"Bearer {a['access_token']}"},
    )
    assert r.status_code == 201
    alice_company_id = r.json()["id"]

    r = client.get(
        f"/api/v1/companies/{alice_company_id}",
        headers={"Authorization": f"Bearer {b['access_token']}"},
    )
    assert r.status_code == 404
