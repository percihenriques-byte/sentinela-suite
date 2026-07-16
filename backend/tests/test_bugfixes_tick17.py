"""Regression tests for the tick-17 review pass."""


def test_field_is_optional_rejects_bool_none():
    """A required-but-defaulted field like `is_active: bool` must NOT be
    treated as optional. Prior implementation would clobber it with None."""
    from app.models import LeadScoringRule
    from app.services.crud import _field_is_optional

    obj = LeadScoringRule(
        workspace_id="00000000-0000-0000-0000-000000000000",
        name="x", field="source", op="iequals",
    )
    # `is_active: bool = Field(default=True)` — cannot be None.
    assert _field_is_optional(obj, "is_active") is False
    # `value: Optional[str] = None` — is genuinely nullable.
    assert _field_is_optional(obj, "value") is True
    # Unknown key — caller skips anyway.
    assert _field_is_optional(obj, "nonexistent") is True


def test_apply_updates_does_not_clobber_bool_with_none():
    from app.models import LeadScoringRule
    from app.services.crud import apply_updates

    rule = LeadScoringRule(
        workspace_id="00000000-0000-0000-0000-000000000000",
        name="x", field="source", op="iequals", is_active=True,
    )
    # A caller passing `is_active: None` should NOT nuke the bool.
    apply_updates(rule, {"is_active": None, "name": "renamed"},
                  allowed={"is_active", "name"})
    assert rule.is_active is True
    assert rule.name == "renamed"

    # But passing None for a genuinely-optional field DOES clear it.
    apply_updates(rule, {"value": None}, allowed={"value"})
    assert rule.value is None


def test_find_contact_does_not_hijack_bare_word(auth_client):
    """Before fix: any message containing "contact" (e.g. "log contact call")
    would route to find_contact intent because the regex had unbalanced |."""
    # A message that DOES want find_contact still works.
    resp = auth_client.post("/api/v1/contacts", json={"first_name": "Zoe"})
    assert resp.status_code == 201
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "find contact Zoe"}).json()
    assert r["intent"] == "find_contact"

    # A message that mentions "contact" incidentally must NOT hit find_contact.
    r = auth_client.post("/api/v1/jarvis/chat",
                        json={"message": "please write me a haiku about a contact"}).json()
    assert r["intent"] != "find_contact"


def test_bulk_contact_partial_failure_does_not_poison_transaction(auth_client):
    """One bad row (dangling company_id) must not sink the others.
    Before fix: session state was broken after flush failure."""
    import uuid as _uuid
    fake_company = str(_uuid.uuid4())
    resp = auth_client.post("/api/v1/contacts/bulk", json={
        "items": [
            {"first_name": "Good One"},
            {"first_name": "Bad One", "company_id": fake_company},
            {"first_name": "Good Two"},
        ]
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["created"] == 2, body
    assert body["failed"] == 1, body
    contacts = auth_client.get("/api/v1/contacts").json()
    names = {c["first_name"] for c in contacts["items"]}
    assert "Good One" in names and "Good Two" in names
    assert "Bad One" not in names
