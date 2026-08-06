"""Lead scoring evaluator.

Kept intentionally small and side-effect-free (no DB writes) so it can be
called from CRUD paths, the recalculate endpoint, and Jarvis tools uniformly.
Callers persist the resulting score themselves.
"""
from __future__ import annotations

import re
from typing import Any, Iterable
from uuid import UUID
from sqlmodel import Session, select

from app.models import Lead, LeadScoringRule


def _lead_field(lead: Lead, field: str) -> Any:
    """Extract the value a rule is checking against."""
    if field == "email_domain":
        if not lead.email or "@" not in lead.email:
            return None
        return lead.email.rsplit("@", 1)[-1].lower()
    if field == "score":
        return lead.score
    if field == "status":
        return lead.status.value if hasattr(lead.status, "value") else str(lead.status)
    return getattr(lead, field, None)


def _match(op: str, actual: Any, expected: str | None) -> bool:
    if op == "is_present":
        return actual is not None and actual != ""
    if op == "is_absent":
        return actual is None or actual == ""
    if expected is None:
        return False
    actual_str = "" if actual is None else str(actual)
    lo_a = actual_str.lower()
    lo_e = expected.lower()

    if op == "equals":
        return actual_str == expected
    if op == "iequals":
        return lo_a == lo_e
    if op == "contains":
        return expected in actual_str
    if op == "icontains":
        return lo_e in lo_a
    if op == "startswith":
        return actual_str.startswith(expected)
    if op == "endswith":
        return actual_str.endswith(expected)
    if op == "regex":
        try:
            return re.search(expected, actual_str, re.IGNORECASE) is not None
        except re.error:
            return False
    if op == "in":
        options = {v.strip().lower() for v in expected.split(",") if v.strip()}
        return lo_a in options
    if op in ("gt", "gte", "lt", "lte"):
        try:
            an = float(actual_str)
            en = float(expected)
        except (TypeError, ValueError):
            return False
        return {"gt": an > en, "gte": an >= en, "lt": an < en, "lte": an <= en}[op]
    return False


def evaluate(rules: Iterable[LeadScoringRule], lead: Lead) -> tuple[int, list[dict[str, Any]]]:
    """Return (total_delta, matches). Matches are ordered by rule.order_index."""
    ordered = sorted(rules, key=lambda r: (r.order_index, r.created_at))
    total = 0
    matches: list[dict[str, Any]] = []
    for rule in ordered:
        if not rule.is_active or rule.deleted_at is not None:
            continue
        actual = _lead_field(lead, rule.field)
        if _match(rule.op, actual, rule.value):
            total += int(rule.score_delta)
            matches.append({"id": str(rule.id), "name": rule.name, "delta": int(rule.score_delta)})
    return total, matches


def load_active_rules(session: Session, workspace_id: UUID) -> list[LeadScoringRule]:
    stmt = (
        select(LeadScoringRule)
        .where(
            LeadScoringRule.workspace_id == workspace_id,
            LeadScoringRule.deleted_at.is_(None),
            LeadScoringRule.is_active.is_(True),
        )
        .order_by(LeadScoringRule.order_index.asc())
    )
    return list(session.exec(stmt).all())


def recompute_lead_score(session: Session, lead: Lead, base_score: int | None = None) -> tuple[int, list[dict[str, Any]]]:
    """Recompute and persist a single lead's score.

    `base_score` — the starting number before rules add on. If None, we take the
    lead's current score minus the delta from any previous match evaluation. In
    practice we treat the current stored score as the base and just add rules
    on top *once* per recompute — callers who want a clean recompute should
    reset the lead.score first.
    """
    base = lead.score if base_score is None else int(base_score)
    rules = load_active_rules(session, lead.workspace_id)
    delta, matches = evaluate(rules, lead)
    lead.score = base + delta
    session.add(lead)
    return lead.score, matches


def recompute_all(session: Session, workspace_id: UUID, reset_to_zero: bool = True) -> dict[str, Any]:
    rules = load_active_rules(session, workspace_id)
    stmt = select(Lead).where(Lead.workspace_id == workspace_id, Lead.deleted_at.is_(None))
    leads = list(session.exec(stmt).all())
    updated = 0
    for lead in leads:
        base = 0 if reset_to_zero else lead.score
        delta, _ = evaluate(rules, lead)
        new_score = base + delta
        if new_score != lead.score:
            lead.score = new_score
            session.add(lead)
            updated += 1
    session.commit()
    return {"rules_active": len(rules), "leads_scanned": len(leads), "leads_updated": updated}
