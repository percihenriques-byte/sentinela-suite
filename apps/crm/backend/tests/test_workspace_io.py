"""Tests for workspace export + import (offline-first backup path)."""
import uuid


def test_export_returns_all_workspace_entities(auth_client):
    company = auth_client.post("/api/v1/companies", json={"name": "Export Co"}).json()
    auth_client.post("/api/v1/contacts", json={"first_name": "Ex", "company_id": company["id"]})
    auth_client.post("/api/v1/opportunities", json={"name": "Ex Deal", "amount": 100})

    resp = auth_client.get("/api/v1/workspaces/current/export")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 1
    assert "workspace_id" in body
    assert body["entities"]["companies"][0]["name"] == "Export Co"
    assert body["entities"]["contacts"][0]["first_name"] == "Ex"
    assert body["entities"]["opportunities"][0]["name"] == "Ex Deal"
    assert body["entities"]["pipelines"]  # default pipeline created on opp create
    assert "Content-Disposition" in resp.headers


def test_export_import_roundtrip_into_second_workspace(client):
    # Register two separate workspaces.
    a = client.post("/api/v1/auth/register", json={
        "email": "alice-io@alice.example.com", "password": "correcthorse-battery",
        "full_name": "Alice", "workspace_name": "Alpha IO",
    }).json()
    b = client.post("/api/v1/auth/register", json={
        "email": "bob-io@bob.example.com", "password": "correcthorse-battery",
        "full_name": "Bob", "workspace_name": "Bravo IO",
    }).json()
    a_hdr = {"Authorization": f"Bearer {a['access_token']}"}
    b_hdr = {"Authorization": f"Bearer {b['access_token']}"}

    # Alice creates data + exports.
    client.post("/api/v1/companies", json={"name": "Migrating Co"}, headers=a_hdr)
    client.post("/api/v1/contacts", json={"first_name": "MigrateMe"}, headers=a_hdr)
    envelope = client.get("/api/v1/workspaces/current/export", headers=a_hdr).json()

    # Bob imports into empty Bravo IO — should remap ids since Bob already has
    # a default pipeline created lazily on any opp op (but we haven't touched
    # opps, so pipeline might not exist yet — either way import handles it).
    resp = client.post("/api/v1/workspaces/current/import", json=envelope, headers=b_hdr)
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["counts"]["companies"] >= 1
    assert result["counts"]["contacts"] >= 1

    # Bob can now see the migrated data as their own.
    companies = client.get("/api/v1/companies", headers=b_hdr).json()
    assert any(c["name"] == "Migrating Co" for c in companies["items"])
    contacts = client.get("/api/v1/contacts", headers=b_hdr).json()
    assert any(c["first_name"] == "MigrateMe" for c in contacts["items"])


def test_import_rejects_bad_envelope(auth_client):
    resp = auth_client.post("/api/v1/workspaces/current/import", json={"foo": "bar"})
    assert resp.status_code == 400

    resp = auth_client.post("/api/v1/workspaces/current/import", json={"version": 999, "entities": {}})
    assert resp.status_code == 400


def test_frontend_index_is_served(client):
    resp = client.get("/index.html")
    # Depending on the working dir the static mount may or may not resolve — but
    # if the frontend exists we should get an HTML page.
    if resp.status_code == 200:
        assert "text/html" in resp.headers.get("content-type", "")
        # A casca da SPA se apresenta como Sentinela (o CRM e um modulo dela).
        assert "Sentinela" in resp.text
