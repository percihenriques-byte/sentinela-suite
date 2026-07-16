"""Tests for bulk create endpoints + Tags CRUD."""


def test_bulk_create_contacts(auth_client):
    resp = auth_client.post("/api/v1/contacts/bulk", json={
        "items": [
            {"first_name": "Ann"},
            {"first_name": "Bob", "email": "bob@example.com"},
            {"first_name": "Cid", "email": "cid@example.com"},
        ]
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["created"] == 3
    assert body["failed"] == 0
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["total"] == 3


def test_bulk_create_companies_reports_errors(auth_client):
    resp = auth_client.post("/api/v1/companies/bulk", json={
        "items": [
            {"name": "Good Co"},
            {"name": ""},  # invalid (min_length=1)
        ]
    })
    # Pydantic validates min_length=1 at request-parse time, so the whole
    # payload is rejected before we hit the handler.
    assert resp.status_code == 422


def test_bulk_create_companies_ok(auth_client):
    resp = auth_client.post("/api/v1/companies/bulk", json={
        "items": [{"name": "One"}, {"name": "Two"}, {"name": "Three"}]
    })
    assert resp.status_code == 201
    assert resp.json()["created"] == 3


def test_tag_lifecycle(auth_client):
    tag = auth_client.post("/api/v1/tags", json={"name": "VIP", "color": "#ff0"}).json()
    contact = auth_client.post("/api/v1/contacts", json={"first_name": "Vera"}).json()

    # Attach
    r = auth_client.post(f"/api/v1/tags/{tag['id']}/attach",
                         json={"subject_type": "contact", "subject_id": contact["id"]})
    assert r.status_code == 201

    # Duplicate attach is idempotent
    r = auth_client.post(f"/api/v1/tags/{tag['id']}/attach",
                         json={"subject_type": "contact", "subject_id": contact["id"]})
    assert r.json()["already_linked"] is True

    # Query tags for subject
    tags_of = auth_client.get(f"/api/v1/tags/for/contact/{contact['id']}").json()
    assert len(tags_of) == 1
    assert tags_of[0]["name"] == "VIP"

    # Detach
    r = auth_client.post(f"/api/v1/tags/{tag['id']}/detach",
                         json={"subject_type": "contact", "subject_id": contact["id"]})
    assert r.status_code == 204
    tags_of = auth_client.get(f"/api/v1/tags/for/contact/{contact['id']}").json()
    assert tags_of == []


def test_tag_create_is_idempotent_on_name(auth_client):
    a = auth_client.post("/api/v1/tags", json={"name": "Same"}).json()
    b = auth_client.post("/api/v1/tags", json={"name": "Same"}).json()
    assert a["id"] == b["id"]


def test_tag_invalid_subject_type(auth_client):
    tag = auth_client.post("/api/v1/tags", json={"name": "X"}).json()
    r = auth_client.post(f"/api/v1/tags/{tag['id']}/attach",
                         json={"subject_type": "bogus", "subject_id": tag["id"]})
    assert r.status_code == 400
