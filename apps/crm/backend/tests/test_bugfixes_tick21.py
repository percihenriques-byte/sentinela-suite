"""Regression tests for the tick-21 review pass."""


def test_workflow_corrupted_trigger_logs_warning(auth_client, caplog):
    """A workflow with malformed trigger_json used to be silently skipped —
    now logs at WARNING so operators can spot the fault."""
    import logging
    from app import models
    from app.db.session import engine
    from sqlmodel import Session

    # Insert a workflow with garbage trigger_json directly (the endpoint
    # validates JSON up front, so we have to bypass it to simulate a manual
    # DB edit / corruption).
    with Session(engine) as s:
        # Grab any workspace via a registered user.
        ws_row = s.exec(models.__dict__["Workspace"].__table__.select()).first()
        assert ws_row is not None
        wf = models.Workflow(
            workspace_id=ws_row.id,
            name="broken",
            trigger_json="{not-valid-json",
            is_active=True,
        )
        s.add(wf)
        s.commit()

    with caplog.at_level(logging.WARNING, logger="jarvis.workflow"):
        # Trigger any activity so evaluate_workflows_for_activity runs.
        auth_client.post("/api/v1/companies", json={"name": "Trigger"})
    assert any("workflow_trigger_json_invalid" in r.message for r in caplog.records)


def test_workflow_steps_stable_order_with_same_order_index(auth_client):
    """If multiple steps share order_index, secondary sort by created_at keeps
    the sequence deterministic."""
    wf = auth_client.post("/api/v1/workflows", json={
        "name": "ordered",
        "trigger": {"kind": "created", "subject_type": "company"},
        "steps": [
            {"kind": "add_note", "payload": {"body": "first"}},
            {"kind": "add_note", "payload": {"body": "second"}},
            {"kind": "add_note", "payload": {"body": "third"}},
        ],
    }).json()
    # Fetch back — all default order_index=0, but insert order should hold.
    listed = auth_client.get("/api/v1/workflows").json()
    steps = next(x for x in listed["items"] if x["id"] == wf["id"])["steps"]
    payloads = [s["payload_json"] for s in steps]
    assert '"first"' in payloads[0]
    assert '"second"' in payloads[1]
    assert '"third"' in payloads[2]


def test_taglink_attach_is_idempotent(auth_client):
    """The uniqueness guarantee. Even without racing requests we should return
    already_linked=True on a repeat attach."""
    tag = auth_client.post("/api/v1/tags", json={"name": "VIP"}).json()
    contact = auth_client.post("/api/v1/contacts", json={"first_name": "Zed"}).json()
    r1 = auth_client.post(f"/api/v1/tags/{tag['id']}/attach",
                          json={"subject_type": "contact", "subject_id": contact["id"]})
    assert r1.status_code == 201
    r2 = auth_client.post(f"/api/v1/tags/{tag['id']}/attach",
                          json={"subject_type": "contact", "subject_id": contact["id"]})
    assert r2.status_code == 201
    assert r2.json()["already_linked"] is True
