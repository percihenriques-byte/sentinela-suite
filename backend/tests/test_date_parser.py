"""Unit tests for the local NL date parser."""
from datetime import datetime, timedelta, timezone

from app.jarvis.date_parser import parse_when


REF = datetime(2026, 7, 11, 10, 0, 0, tzinfo=timezone.utc)  # a Saturday


def test_today_default_hour():
    dt = parse_when("today", now=REF)
    assert dt is not None
    assert dt.date() == REF.date()
    assert dt.hour == 9


def test_tomorrow_with_time():
    dt = parse_when("tomorrow 3pm", now=REF)
    assert dt is not None
    assert dt.date() == (REF + timedelta(days=1)).date()
    assert dt.hour == 15
    assert dt.minute == 0


def test_next_monday_at_15_30():
    dt = parse_when("next monday at 15:30", now=REF)
    assert dt is not None
    # REF is Saturday (weekday=5). Next Monday is 2 days later.
    assert dt.weekday() == 0
    assert dt > REF
    assert dt.hour == 15 and dt.minute == 30


def test_iso_date_with_time():
    dt = parse_when("2026-08-01 at 9am", now=REF)
    assert dt is not None
    assert (dt.year, dt.month, dt.day) == (2026, 8, 1)
    assert dt.hour == 9


def test_bare_time_defaults_to_next_occurrence():
    dt = parse_when("11:30", now=REF)
    assert dt is not None
    assert dt.date() == REF.date()  # 11:30 today (still ahead of 10:00)
    assert (dt.hour, dt.minute) == (11, 30)

    dt = parse_when("9:00", now=REF)
    assert dt is not None
    assert dt.date() == (REF + timedelta(days=1)).date()  # 9am already past → tomorrow


def test_portuguese_amanha_15h():
    dt = parse_when("amanhã 15h", now=REF)
    assert dt is not None
    assert dt.date() == (REF + timedelta(days=1)).date()
    assert dt.hour == 15 and dt.minute == 0


def test_unparseable_returns_none():
    assert parse_when("some day next quarter", now=REF) is None
    assert parse_when("", now=REF) is None
