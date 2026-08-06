from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from sqlmodel import Session, select, func

from app.models import (
    Contact,
    Company,
    Lead,
    Opportunity,
    Task,
    Meeting,
    Activity,
    OpportunityStatus,
    TaskStatus,
    JarvisMemory,
)


@dataclass
class WorkspaceSnapshot:
    """Lightweight snapshot used to prime Jarvis on each turn.

    Kept intentionally small — the model does semantic retrieval through tools
    when it needs specifics. This is orientation, not a full data dump.
    """
    workspace_id: UUID
    user_id: UUID
    generated_at: datetime
    counts: dict[str, int] = field(default_factory=dict)
    overdue_tasks: list[dict[str, Any]] = field(default_factory=list)
    upcoming_meetings: list[dict[str, Any]] = field(default_factory=list)
    open_opportunities: list[dict[str, Any]] = field(default_factory=list)
    preferences: dict[str, str] = field(default_factory=dict)
    nudges: list[dict[str, Any]] = field(default_factory=list)

    def as_system_message(self) -> str:
        parts: list[str] = []
        parts.append("You are Jarvis, an AI assistant embedded in a CRM.")
        parts.append("You help the user run their business. Be concise, actionable, and honest about uncertainty.")
        parts.append("When you need specifics, call a tool rather than guessing.")
        parts.append("")
        parts.append(f"Workspace snapshot (generated {self.generated_at.isoformat()}):")
        parts.append(f"- Totals: {self.counts}")
        if self.overdue_tasks:
            parts.append(f"- {len(self.overdue_tasks)} overdue tasks; nearest few:")
            for t in self.overdue_tasks[:5]:
                parts.append(f"  * {t['title']} (due {t['due_at']})")
        if self.upcoming_meetings:
            parts.append(f"- Upcoming meetings in the next 48h:")
            for m in self.upcoming_meetings[:5]:
                parts.append(f"  * {m['title']} at {m['starts_at']}")
        if self.open_opportunities:
            parts.append(f"- {len(self.open_opportunities)} open opportunities (top by amount):")
            for o in self.open_opportunities[:5]:
                parts.append(f"  * {o['name']} — {o['amount']} {o['currency']}")
        if self.preferences:
            parts.append("- Learned user preferences:")
            for k, v in self.preferences.items():
                parts.append(f"  * {k}: {v}")
        return "\n".join(parts)


def _count(session: Session, model, workspace_id: UUID) -> int:
    stmt = select(func.count()).select_from(model).where(
        model.workspace_id == workspace_id,
        model.deleted_at.is_(None),
    )
    return session.exec(stmt).one()


def build_workspace_context(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    now: datetime | None = None,
) -> WorkspaceSnapshot:
    now = now or datetime.now(timezone.utc)
    snap = WorkspaceSnapshot(workspace_id=workspace_id, user_id=user_id, generated_at=now)

    snap.counts = {
        "contacts": _count(session, Contact, workspace_id),
        "companies": _count(session, Company, workspace_id),
        "leads": _count(session, Lead, workspace_id),
        "opportunities": _count(session, Opportunity, workspace_id),
        "tasks_open": session.exec(
            select(func.count()).select_from(Task).where(
                Task.workspace_id == workspace_id,
                Task.deleted_at.is_(None),
                Task.status.in_([TaskStatus.todo, TaskStatus.in_progress, TaskStatus.blocked]),
            )
        ).one(),
    }

    overdue_stmt = (
        select(Task)
        .where(
            Task.workspace_id == workspace_id,
            Task.deleted_at.is_(None),
            Task.due_at.is_not(None),
            Task.due_at < now,
            Task.status.in_([TaskStatus.todo, TaskStatus.in_progress, TaskStatus.blocked]),
        )
        .order_by(Task.due_at.asc())
        .limit(10)
    )
    snap.overdue_tasks = [
        {"id": str(t.id), "title": t.title, "due_at": t.due_at.isoformat() if t.due_at else None}
        for t in session.exec(overdue_stmt).all()
    ]

    horizon = now + timedelta(hours=48)
    meetings_stmt = (
        select(Meeting)
        .where(
            Meeting.workspace_id == workspace_id,
            Meeting.deleted_at.is_(None),
            Meeting.starts_at >= now,
            Meeting.starts_at <= horizon,
        )
        .order_by(Meeting.starts_at.asc())
        .limit(10)
    )
    snap.upcoming_meetings = [
        {"id": str(m.id), "title": m.title, "starts_at": m.starts_at.isoformat()}
        for m in session.exec(meetings_stmt).all()
    ]

    opps_stmt = (
        select(Opportunity)
        .where(
            Opportunity.workspace_id == workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
        )
        .order_by(Opportunity.amount.desc())
        .limit(10)
    )
    snap.open_opportunities = [
        {"id": str(o.id), "name": o.name, "amount": o.amount, "currency": o.currency}
        for o in session.exec(opps_stmt).all()
    ]

    # Latest preference per key wins. Include 'preference' and 'style' so tone
    # settings (set_tone intent) surface in snap.preferences['tone'].
    mem_stmt = (
        select(JarvisMemory)
        .where(
            JarvisMemory.workspace_id == workspace_id,
            JarvisMemory.user_id == user_id,
            JarvisMemory.deleted_at.is_(None),
            JarvisMemory.kind.in_(["preference", "style"]),
        )
        .order_by(JarvisMemory.created_at.desc())
        .limit(50)
    )
    for m in session.exec(mem_stmt).all():
        snap.preferences.setdefault(m.key, m.value)

    snap.nudges = _build_nudges(session, workspace_id, user_id, snap, now)

    return snap


def _build_nudges(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    snap: WorkspaceSnapshot,
    now: datetime,
) -> list[dict[str, Any]]:
    """Small, actionable prompts Jarvis wants the user to notice.

    Each nudge has: level (info|warn), message, suggested_prompt (what the user
    can type/click to act on it). Deliberately capped small so the UI stays
    calm.
    """
    nudges: list[dict[str, Any]] = []

    if len(snap.overdue_tasks) >= 3:
        nudges.append({
            "level": "warn",
            "message": f"{len(snap.overdue_tasks)} tasks are overdue",
            "suggested_prompt": "show overdue tasks",
        })

    if snap.upcoming_meetings:
        first = snap.upcoming_meetings[0]
        nudges.append({
            "level": "info",
            "message": f"Next meeting: {first['title']}",
            "suggested_prompt": "upcoming meetings",
        })

    # Hot leads: score >= 70 not yet converted.
    hot_lead = session.exec(
        select(Lead)
        .where(
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
            Lead.score >= 70,
            Lead.converted_at.is_(None),
        )
        .order_by(Lead.score.desc())
        .limit(1)
    ).first()
    if hot_lead is not None:
        who = f"{hot_lead.first_name} {hot_lead.last_name or ''}".strip()
        nudges.append({
            "level": "info",
            "message": f"Hot lead: {who} ({hot_lead.score})",
            "suggested_prompt": f"find contact {who}" if who else "",
        })

    if snap.open_opportunities and not snap.upcoming_meetings and not snap.overdue_tasks:
        nudges.append({
            "level": "info",
            "message": "Nothing on fire — good time to summarize the pipeline",
            "suggested_prompt": "summarize pipeline",
        })

    return nudges
