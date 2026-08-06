"""Regression tests for the tick-27 review pass — datetime tz-safety +
week_summary intent over-matching."""


def test_week_summary_does_not_hijack_meeting_names_with_weekly(auth_client):
    """Before fix: any message containing the bare word 'weekly' hit the
    week_summary intent, so 'reschedule Nebula weekly sync to tomorrow 3pm'
    got summarized instead of rescheduled."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    auth_client.post("/api/v1/meetings", json={
        "title": "Nebula weekly sync",
        "starts_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "ends_at": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
    })
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "reschedule Nebula weekly sync to tomorrow 3pm",
    }).json()
    assert r["intent"] == "reschedule_meeting", r


def test_week_summary_still_matches_this_week(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "this week"}).json()
    assert r["intent"] == "week_summary"


def test_week_summary_still_matches_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "resumo da semana"}).json()
    assert r["intent"] == "week_summary"


def test_reschedule_meeting_aware_iso_datetime_input():
    """The reschedule tool must handle both aware and naive input datetimes
    without a TypeError from mixing timezone info downstream."""
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    from sqlmodel import SQLModel, Session
    from app.db.session import engine
    from app import models  # noqa
    from app.jarvis.tools import _reschedule_meeting, ToolContext

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        user = models.User(email="rt@example.com", password_hash="x")
        s.add(user); s.flush()
        ws = models.Workspace(name="RT", slug="rt", owner_id=user.id)
        s.add(ws); s.flush()
        now = datetime.now(timezone.utc)
        m = models.Meeting(
            workspace_id=ws.id, title="Standup",
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
        )
        s.add(m); s.commit(); s.refresh(m)
        meeting_id = m.id

        ctx = ToolContext(session=s, workspace_id=ws.id, user_id=user.id)
        # aware ISO with Z suffix
        result = _reschedule_meeting(ctx, {
            "meeting_id": str(meeting_id),
            "starts_at": (now + timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
        })
        assert "error" not in result, result
        assert result["title"] == "Standup"
