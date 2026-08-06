"""Regression tests for the tick-25 review pass — cross-workspace FK guard."""


def test_convert_lead_rejects_cross_workspace_company_id(client):
    """User A tries to convert a lead but supplies a company_id owned by
    workspace B. Before fix: contact + opportunity were created referencing
    the foreign company. Now: 404."""
    a = client.post("/api/v1/auth/register", json={
        "email": "alice-xw@alice.example.com", "password": "correcthorse-battery",
        "full_name": "Alice", "workspace_name": "Alpha XW",
    }).json()
    b = client.post("/api/v1/auth/register", json={
        "email": "bob-xw@bob.example.com", "password": "correcthorse-battery",
        "full_name": "Bob", "workspace_name": "Bravo XW",
    }).json()
    a_hdr = {"Authorization": f"Bearer {a['access_token']}"}
    b_hdr = {"Authorization": f"Bearer {b['access_token']}"}

    # B creates a company Alice can't see.
    b_company = client.post("/api/v1/companies", json={"name": "Foreign Co"}, headers=b_hdr).json()

    # A creates a lead.
    lead = client.post("/api/v1/leads", json={"first_name": "Target"}, headers=a_hdr).json()

    # A tries to attach B's company.
    r = client.post(f"/api/v1/leads/{lead['id']}/convert", json={
        "company_id": b_company["id"],
        "create_opportunity": False,
    }, headers=a_hdr)
    assert r.status_code == 404, r.text
    # Lead should NOT be converted.
    same = client.get(f"/api/v1/leads/{lead['id']}", headers=a_hdr).json()
    assert same["status"] != "converted"


def test_convert_lead_rejects_cross_workspace_pipeline_id(client):
    a = client.post("/api/v1/auth/register", json={
        "email": "alice-xw2@alice.example.com", "password": "correcthorse-battery",
        "full_name": "Alice", "workspace_name": "Alpha XW2",
    }).json()
    b = client.post("/api/v1/auth/register", json={
        "email": "bob-xw2@bob.example.com", "password": "correcthorse-battery",
        "full_name": "Bob", "workspace_name": "Bravo XW2",
    }).json()
    a_hdr = {"Authorization": f"Bearer {a['access_token']}"}
    b_hdr = {"Authorization": f"Bearer {b['access_token']}"}

    # B has a pipeline (auto-created on first pipelines fetch).
    b_pipeline = client.get("/api/v1/pipelines", headers=b_hdr).json()[0]

    lead = client.post("/api/v1/leads", json={"first_name": "Target"}, headers=a_hdr).json()

    r = client.post(f"/api/v1/leads/{lead['id']}/convert", json={
        "pipeline_id": b_pipeline["id"],
    }, headers=a_hdr)
    assert r.status_code == 404, r.text


def test_convert_lead_still_works_with_own_workspace_ids(auth_client):
    """Sanity: the validator doesn't block the happy path."""
    company = auth_client.post("/api/v1/companies", json={"name": "Own Co"}).json()
    pipeline = auth_client.get("/api/v1/pipelines").json()[0]
    lead = auth_client.post("/api/v1/leads", json={"first_name": "Ok"}).json()
    r = auth_client.post(f"/api/v1/leads/{lead['id']}/convert", json={
        "company_id": company["id"],
        "pipeline_id": pipeline["id"],
    })
    assert r.status_code == 200, r.text


def test_workflow_invalid_lead_status_logs_warning(auth_client, caplog):
    """Before fix: a workflow with `set_lead_status: 'bogus'` silently no-op'd
    every time it fired."""
    import logging

    auth_client.post("/api/v1/workflows", json={
        "name": "bad status",
        "trigger": {"kind": "created", "subject_type": "lead"},
        "steps": [{"kind": "set_lead_status", "payload": {"status": "not-a-real-status"}}],
    })
    with caplog.at_level(logging.WARNING, logger="jarvis.workflow"):
        auth_client.post("/api/v1/leads", json={"first_name": "X"})
    assert any("workflow_set_lead_status_invalid" in r.message for r in caplog.records)
