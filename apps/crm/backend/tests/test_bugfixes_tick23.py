"""Regression tests for the tick-23 review pass."""


def test_patch_opportunity_pipeline_only_does_not_400(auth_client):
    """Before fix: PATCH /opportunities/{id} with only pipeline_id would fail
    with `stage_not_in_pipeline` because the resolver was handed the old
    stage_id against the new pipeline."""
    # Seed a second pipeline so we have somewhere to move to.
    from app import models
    from app.db.session import engine
    from sqlmodel import Session

    p1 = auth_client.get("/api/v1/pipelines").json()[0]
    with Session(engine) as s:
        ws_row = s.exec(models.Workspace.__table__.select()).first()
        p2 = models.Pipeline(workspace_id=ws_row.id, name="Alt Pipeline")
        s.add(p2); s.flush()
        for i, name in enumerate(("Discovery", "Demo", "Close")):
            s.add(models.PipelineStage(
                workspace_id=ws_row.id, pipeline_id=p2.id,
                name=name, order_index=i, probability=25 * (i + 1),
            ))
        s.commit()
        p2_id = p2.id

    opp = auth_client.post("/api/v1/opportunities", json={
        "name": "Move me", "amount": 1000,
    }).json()

    r = auth_client.patch(f"/api/v1/opportunities/{opp['id']}",
                          json={"pipeline_id": str(p2_id)})
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["pipeline_id"] == str(p2_id)
    # Stage should have been reset to the first stage of the new pipeline.
    p2_stages = [x for x in auth_client.get("/api/v1/pipelines").json() if x["id"] == str(p2_id)][0]["stages"]
    p2_first = min(p2_stages, key=lambda s: s["order_index"])
    assert updated["stage_id"] == p2_first["id"]


def test_update_meeting_rejects_null_datetimes(auth_client):
    """Explicit `{"starts_at": null}` in PATCH used to crash with a TypeError
    inside _validate_window; must now return 400."""
    from datetime import datetime, timedelta, timezone

    def _iso(d):
        return d.isoformat().replace("+00:00", "Z")

    now = datetime.now(timezone.utc)
    meeting = auth_client.post("/api/v1/meetings", json={
        "title": "Sync", "starts_at": _iso(now + timedelta(hours=1)),
        "ends_at": _iso(now + timedelta(hours=2)),
    }).json()

    for body in ({"starts_at": None}, {"ends_at": None}):
        r = auth_client.patch(f"/api/v1/meetings/{meeting['id']}", json=body)
        assert r.status_code == 400, f"{body} → {r.status_code}"
