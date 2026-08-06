"""Tiny, dependency-free natural-language date parser for Jarvis.

Handles the surface area users actually type:

  today | tomorrow | day after tomorrow
  Monday, Tue, next monday
  YYYY-MM-DD
  DD/MM (assumes current year, or next year if in the past)
  DD/MM/YYYY, DD/MM/YY
  at 3pm | at 15:00 | 3 PM | 3:30 pm | 15h30 | 15h

Portuguese variants:
  hoje | amanhã | depois de amanhã
  segunda | terça | quarta | quinta | sexta | sábado | domingo
  às 15h | às 15h30 | ao meio-dia

Returns a timezone-aware UTC datetime, or None if unparseable.

Deliberately conservative: when ambiguous we prefer the *nearest future* time.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone


_WEEKDAYS_EN = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}
_WEEKDAYS_PT = {
    "segunda": 0, "segunda-feira": 0,
    "terça": 1, "terca": 1, "terça-feira": 1, "terca-feira": 1,
    "quarta": 2, "quarta-feira": 2,
    "quinta": 3, "quinta-feira": 3,
    "sexta": 4, "sexta-feira": 4,
    "sábado": 5, "sabado": 5,
    "domingo": 6,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _next_weekday(base: date, target: int, force_next_week: bool = False) -> date:
    days_ahead = (target - base.weekday()) % 7
    if days_ahead == 0 and not force_next_week:
        days_ahead = 0  # today
    elif days_ahead == 0 and force_next_week:
        days_ahead = 7
    return base + timedelta(days=days_ahead or (7 if force_next_week else 0))


def _extract_time(text: str) -> tuple[time | None, str]:
    """Return (parsed time, remaining text with the time snippet removed)."""
    # Matches: 3pm, 3 PM, 3:30 pm, 15:00, 15h, 15h30, 15h00
    # Order matters — try the AM/PM pattern first. Otherwise "3:30 pm" gets
    # gobbled by the 24-hour pattern (matching "3:30" as h=3 m=30) and the "pm"
    # marker is silently dropped, leaving the caller with a 3am time instead of
    # 15:30. This bug was caught in tick 22.
    patterns = [
        # 3pm, 3 PM, 3:30 pm, 12 am
        re.compile(r"\b(?P<h>1[0-2]|0?[1-9])(?:\s*[:h]\s*(?P<m>[0-5]\d))?\s*(?P<ampm>am|pm)\b", re.IGNORECASE),
        # 15:30 or 15h30 or 15h
        re.compile(r"\b(?P<h>[01]?\d|2[0-3])\s*(?:[:h])\s*(?P<m>[0-5]\d)\b", re.IGNORECASE),
        re.compile(r"\b(?P<h>[01]?\d|2[0-3])\s*h\b", re.IGNORECASE),
    ]
    for p in patterns:
        m = p.search(text)
        if not m:
            continue
        h = int(m.group("h"))
        minute = int(m.group("m") or 0) if "m" in m.groupdict() else 0
        ampm = m.groupdict().get("ampm")
        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and h < 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
        if 0 <= h <= 23 and 0 <= minute <= 59:
            remaining = (text[: m.start()] + text[m.end():]).strip()
            return time(hour=h, minute=minute), remaining
    return None, text


def _extract_date(text: str, ref: datetime) -> tuple[date | None, str]:
    ref_date = ref.date()
    lowered = text.lower().strip()

    # Anchors: today / tomorrow / day after tomorrow
    anchors = [
        (r"\b(day after tomorrow|depois de amanh[aã])\b", 2),
        (r"\b(tomorrow|amanh[aã])\b", 1),
        (r"\b(today|hoje)\b", 0),
    ]
    for pat, offset in anchors:
        m = re.search(pat, lowered)
        if m:
            remaining = (text[: m.start()] + text[m.end():]).strip()
            return ref_date + timedelta(days=offset), remaining

    # "noon" / "meio-dia" — implicit today; time is handled elsewhere.

    # Weekdays
    for wds in (_WEEKDAYS_PT, _WEEKDAYS_EN):
        for name, dow in wds.items():
            # "next monday" / "próxima segunda"
            m = re.search(rf"\b(?:next|pr[óo]xima?)\s+{re.escape(name)}\b", lowered)
            if m:
                remaining = (text[: m.start()] + text[m.end():]).strip()
                return _next_weekday(ref_date, dow, force_next_week=True), remaining
            m = re.search(rf"\b{re.escape(name)}\b", lowered)
            if m:
                remaining = (text[: m.start()] + text[m.end():]).strip()
                return _next_weekday(ref_date, dow, force_next_week=False), remaining

    # ISO YYYY-MM-DD
    m = re.search(r"\b(?P<y>\d{4})-(?P<mo>\d{1,2})-(?P<d>\d{1,2})\b", text)
    if m:
        try:
            d = date(int(m.group("y")), int(m.group("mo")), int(m.group("d")))
            remaining = (text[: m.start()] + text[m.end():]).strip()
            return d, remaining
        except ValueError:
            pass

    # DD/MM or DD/MM/YY(YY)
    m = re.search(r"\b(?P<d>\d{1,2})/(?P<mo>\d{1,2})(?:/(?P<y>\d{2,4}))?\b", text)
    if m:
        try:
            day = int(m.group("d"))
            month = int(m.group("mo"))
            year_raw = m.group("y")
            if year_raw:
                year = int(year_raw)
                if year < 100:
                    year += 2000
            else:
                year = ref_date.year
            candidate = date(year, month, day)
            if not year_raw and candidate < ref_date:
                candidate = date(year + 1, month, day)
            remaining = (text[: m.start()] + text[m.end():]).strip()
            return candidate, remaining
        except ValueError:
            pass

    return None, text


def parse_when(text: str, *, now: datetime | None = None, default_hour: int = 9) -> datetime | None:
    """Parse a natural-language date/time expression to an aware UTC datetime.

    Assumes the input is a *snippet* focused on the when — e.g. "tomorrow 3pm"
    or "next monday at 15:00". Callers strip the leading trigger words first.
    """
    if not text or not text.strip():
        return None
    ref = now or _now_utc()

    parsed_time, remaining = _extract_time(text)
    parsed_date, remaining = _extract_date(remaining, ref)

    if parsed_date is None and parsed_time is None:
        return None
    if parsed_date is None:
        # Bare time — assume today, or tomorrow if already past.
        d = ref.date()
        candidate = datetime.combine(d, parsed_time or time(default_hour), tzinfo=timezone.utc)
        if candidate <= ref:
            candidate += timedelta(days=1)
        return candidate

    t = parsed_time or time(hour=default_hour)
    return datetime.combine(parsed_date, t, tzinfo=timezone.utc)
