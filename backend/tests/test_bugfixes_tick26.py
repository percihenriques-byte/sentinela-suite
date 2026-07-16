"""Regression tests for the tick-26 sweep — cross-workspace FK guards on
opportunities, notes, tasks, meetings."""


def _two_workspaces(client):
    """Register two separate workspaces and return their auth headers."""
    a = client.post("/api/v1/auth/register", json={
        "email": "alice-fk@alice.example.com", "password": "correcthorse-battery",
        "full_name": "Alice", "workspace_name": "Alpha FK",
    }).json()
    b = client.post("/api/v1/auth/register", json={
        "email": "bob-fk@bob.example.com", "password": "correcthorse-battery",
        "full_name": "Bob", "workspace_name": "Bravo FK",
    }).json()
    return (
        {"Authorization": f"Bearer {a['access_token']}"},
        {"Authorization": f"Bearer {b['access_token']}"},
    )


def test_opportunity_rejects_foreign_contact(client):
    a, b = _two_workspaces(client)
    foreign_contact = client.post("/api/v1/contacts", json={"first_name": "Ext"}, headers=b).json()
    r = client.post("/api/v1/opportunities", json={
        "name": "Bad", "amount": 100, "contact_id": foreign_contact["id"],
    }, headers=a)
    assert r.status_code == 404


def test_opportunity_rejects_foreign_company(client):
    a, b = _two_workspaces(client)
    foreign_company = client.post("/api/v1/companies", json={"name": "Ext"}, headers=b).json()
    r = client.post("/api/v1/opportunities", json={
        "name": "Bad", "amount": 100, "company_id": foreign_company["id"],
    }, headers=a)
    assert r.status_code == 404


def test_opportunity_patch_rejects_foreign_contact(client):
    a, b = _two_workspaces(client)
    opp = client.post("/api/v1/opportunities", json={"name": "Mine", "amount": 1}, headers=a).json()
    foreign = client.post("/api/v1/contacts", json={"first_name": "Ext"}, headers=b).json()
    r = client.patch(f"/api/v1/opportunities/{opp['id']}", json={
        "contact_id": foreign["id"],
    }, headers=a)
    assert r.status_code == 404


def test_note_rejects_foreign_related_ids(client):
    a, b = _two_workspaces(client)
    for kind, endpoint, key in (
        ("contact", "/api/v1/contacts", "related_contact_id"),
        ("company", "/api/v1/companies", "related_company_id"),
    ):
        foreign = client.post(endpoint, json={"first_name": "X"} if kind == "contact" else {"name": "X"}, headers=b).json()
        r = client.post("/api/v1/notes", json={"body": "bad", key: foreign["id"]}, headers=a)
        assert r.status_code == 404, f"{kind}: {r.status_code}"


def test_task_rejects_foreign_related_ids(client):
    a, b = _two_workspaces(client)
    foreign = client.post("/api/v1/opportunities", json={"name": "Ext", "amount": 1}, headers=b).json()
    r = client.post("/api/v1/tasks", json={
        "title": "Bad", "related_opportunity_id": foreign["id"],
    }, headers=a)
    assert r.status_code == 404


def test_meeting_rejects_foreign_related_ids(client):
    from datetime import datetime, timedelta, timezone
    a, b = _two_workspaces(client)
    now = datetime.now(timezone.utc)
    foreign_contact = client.post("/api/v1/contacts", json={"first_name": "Ext"}, headers=b).json()
    r = client.post("/api/v1/meetings", json={
        "title": "Bad",
        "starts_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "ends_at": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "related_contact_id": foreign_contact["id"],
    }, headers=a)
    assert r.status_code == 404


def test_own_workspace_ids_still_work(auth_client):
    """Sanity across the four endpoints: happy paths still 201."""
    from datetime import datetime, timedelta, timezone
    company = auth_client.post("/api/v1/companies", json={"name": "Own"}).json()
    contact = auth_client.post("/api/v1/contacts", json={"first_name": "Own"}).json()
    opp = auth_client.post("/api/v1/opportunities", json={
        "name": "Own", "amount": 1, "contact_id": contact["id"], "company_id": company["id"],
    })
    assert opp.status_code == 201
    note = auth_client.post("/api/v1/notes", json={
        "body": "own", "related_contact_id": contact["id"],
    })
    assert note.status_code == 201
    task = auth_client.post("/api/v1/tasks", json={
        "title": "own", "related_company_id": company["id"],
    })
    assert task.status_code == 201
    now = datetime.now(timezone.utc)
    meet = auth_client.post("/api/v1/meetings", json={
        "title": "own",
        "starts_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "ends_at": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "related_contact_id": contact["id"],
    })
    assert meet.status_code == 201
