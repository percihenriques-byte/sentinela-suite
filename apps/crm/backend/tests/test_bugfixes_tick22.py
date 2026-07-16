"""Regression tests for the tick-22 review pass."""
from datetime import datetime, timezone


def test_date_parser_ampm_beats_24h_pattern():
    """Before fix: `3:30 pm` was parsed as 03:30 because the 24h regex ran
    first, consumed `3:30`, and the `pm` marker was silently dropped."""
    from app.jarvis.date_parser import parse_when
    ref = datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)  # Saturday morning

    dt = parse_when("3:30 pm", now=ref)
    assert dt is not None
    assert (dt.hour, dt.minute) == (15, 30), f"got {dt}"


def test_date_parser_still_handles_pure_24h():
    """15:30 without an am/pm marker still parses as 24h."""
    from app.jarvis.date_parser import parse_when
    ref = datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)
    dt = parse_when("15:30", now=ref)
    assert dt is not None
    assert (dt.hour, dt.minute) == (15, 30)


def test_date_parser_various_ampm_forms():
    """Sanity: the reordering shouldn't have broken plain am/pm forms."""
    from app.jarvis.date_parser import parse_when
    ref = datetime(2026, 7, 11, 5, 0, tzinfo=timezone.utc)
    for expr, expect in (
        ("3pm", 15),
        ("3 PM", 15),
        ("12 am", 0),
        ("12 pm", 12),
    ):
        dt = parse_when(expr, now=ref)
        assert dt is not None
        assert dt.hour == expect, f"'{expr}' → {dt}"


def test_verify_password_returns_false_on_bad_hash():
    """Corrupted / foreign hash strings must not raise — they should just fail
    verification, so login returns 401 not 500."""
    from app.core.security import verify_password

    for bogus in ("", "not-a-hash", "$argon2id$brokenformat", "\x00\x01"):
        assert verify_password("anything", bogus) is False


def test_verify_password_still_works_on_valid_hash():
    from app.core.security import hash_password, verify_password

    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_login_with_corrupted_user_hash_returns_401(auth_client):
    """End-to-end: if the DB hash is corrupted, POST /login must return 401 —
    not 500. Simulates a schema-change gone wrong or manual DB tinkering."""
    from app import models
    from app.db.session import engine
    from sqlmodel import Session, select

    with Session(engine) as s:
        user = s.exec(select(models.User)).first()
        assert user is not None
        user.password_hash = "$argon2id$this-is-completely-broken"
        s.add(user)
        s.commit()
        email = user.email

    r = auth_client.post("/api/v1/auth/login",
                         json={"email": email, "password": "anything"})
    assert r.status_code == 401, r.status_code
