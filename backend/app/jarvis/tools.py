from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select, or_

from app.services.crud import like_escape
from app.models import (
    Activity,
    Company,
    Contact,
    JarvisMemory,
    Lead,
    Meeting,
    Note,
    Opportunity,
    PipelineStage,
    Tag,
    TagLink,
    Task,
    TaskStatus,
    OpportunityStatus,
)


@dataclass
class ToolContext:
    session: Session
    workspace_id: UUID
    user_id: UUID
    conversation_context: dict | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


@dataclass
class ToolRegistry:
    tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def call(self, name: str, ctx: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self.tools:
            return {"error": f"unknown_tool:{name}"}
        try:
            return self.tools[name].handler(ctx, arguments)
        except Exception as e:  # surface errors to the model so it can retry
            import logging
            logging.getLogger("jarvis.tools").exception("tool_error name=%s", name)
            return {"error": f"{type(e).__name__}: {e}"}


# ---- Built-in tools ---------------------------------------------------------

def _search_contacts(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query: str = (args.get("query") or "").strip()
    limit = min(int(args.get("limit", 10)), 50)
    if not query:
        return {"results": []}
    like = f"%{like_escape(query)}%"
    stmt = (
        select(Contact)
        .where(
            Contact.workspace_id == ctx.workspace_id,
            Contact.deleted_at.is_(None),
            or_(
                Contact.first_name.ilike(like, escape="\\"),
                Contact.last_name.ilike(like, escape="\\"),
                Contact.email.ilike(like, escape="\\"),
                Contact.phone.ilike(like, escape="\\"),
                Contact.job_title.ilike(like, escape="\\"),
            ),
        )
        .limit(limit)
    )
    return {
        "results": [
            {
                "id": str(c.id),
                "name": f"{c.first_name} {c.last_name or ''}".strip(),
                "email": c.email,
                "phone": c.phone,
                "job_title": c.job_title,
            }
            for c in ctx.session.exec(stmt).all()
        ]
    }


def _list_open_opportunities(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(int(args.get("limit", 10)), 50)
    stmt = (
        select(Opportunity)
        .where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
        )
        .order_by(Opportunity.amount.desc())
        .limit(limit)
    )
    return {
        "results": [
            {
                "id": str(o.id),
                "name": o.name,
                "amount": o.amount,
                "currency": o.currency,
                "expected_close_date": o.expected_close_date.isoformat() if o.expected_close_date else None,
                "probability": o.probability,
            }
            for o in ctx.session.exec(stmt).all()
        ]
    }


def _create_task(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    title = (args.get("title") or "").strip()
    if not title:
        return {"error": "title_required"}
    due_at = args.get("due_at")
    due_dt: datetime | None = None
    if due_at:
        try:
            due_dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        except ValueError:
            return {"error": "invalid_due_at"}
    task = Task(
        workspace_id=ctx.workspace_id,
        title=title,
        description=args.get("description"),
        due_at=due_dt,
        assignee_user_id=ctx.user_id,
    )
    ctx.session.add(task)
    ctx.session.commit()
    ctx.session.refresh(task)
    return {"id": str(task.id), "title": task.title, "status": task.status.value if hasattr(task.status, "value") else str(task.status)}


def _summarize_pipeline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    stmt = (
        select(Opportunity)
        .where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
        )
    )
    opps = list(ctx.session.exec(stmt).all())
    total = sum(o.amount for o in opps)
    weighted = sum(o.amount * (o.probability / 100.0 if o.probability > 1 else o.probability) for o in opps)
    by_currency: dict[str, float] = {}
    for o in opps:
        by_currency[o.currency] = by_currency.get(o.currency, 0.0) + o.amount
    return {
        "open_count": len(opps),
        "total_amount": total,
        "weighted_amount": weighted,
        "by_currency": by_currency,
    }


def _search_companies(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query: str = (args.get("query") or "").strip()
    limit = min(int(args.get("limit", 10)), 50)
    if not query:
        return {"results": []}
    like = f"%{like_escape(query)}%"
    stmt = (
        select(Company)
        .where(
            Company.workspace_id == ctx.workspace_id,
            Company.deleted_at.is_(None),
            or_(
                Company.name.ilike(like, escape="\\"),
                Company.domain.ilike(like, escape="\\"),
                Company.industry.ilike(like, escape="\\"),
            ),
        )
        .limit(limit)
    )
    return {
        "results": [
            {
                "id": str(c.id),
                "name": c.name,
                "domain": c.domain,
                "industry": c.industry,
                "website": c.website,
            }
            for c in ctx.session.exec(stmt).all()
        ]
    }


def _create_note(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    body = (args.get("body") or "").strip()
    if not body:
        return {"error": "body_required"}
    note = Note(
        workspace_id=ctx.workspace_id,
        author_user_id=ctx.user_id,
        body=body,
        related_contact_id=_uuid_or_none(args.get("related_contact_id")),
        related_company_id=_uuid_or_none(args.get("related_company_id")),
        related_opportunity_id=_uuid_or_none(args.get("related_opportunity_id")),
        related_lead_id=_uuid_or_none(args.get("related_lead_id")),
    )
    ctx.session.add(note)
    ctx.session.commit()
    ctx.session.refresh(note)
    return {"id": str(note.id), "body": note.body}


def _mark_task_done(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    task_id = _uuid_or_none(args.get("task_id"))
    query = (args.get("query") or "").strip()
    task: Task | None = None
    if task_id is not None:
        task = ctx.session.exec(
            select(Task).where(
                Task.id == task_id,
                Task.workspace_id == ctx.workspace_id,
                Task.deleted_at.is_(None),
            )
        ).first()
    elif query:
        like = f"%{like_escape(query)}%"
        task = ctx.session.exec(
            select(Task)
            .where(
                Task.workspace_id == ctx.workspace_id,
                Task.deleted_at.is_(None),
                Task.title.ilike(like, escape="\\"),
                Task.status != TaskStatus.done,
            )
            .order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc())
            .limit(1)
        ).first()
    if task is None:
        return {"error": "task_not_found"}
    task.status = TaskStatus.done
    task.completed_at = datetime.now(timezone.utc)
    ctx.session.add(task)
    ctx.session.commit()
    ctx.session.refresh(task)
    return {"id": str(task.id), "title": task.title, "status": task.status.value}


def _move_opportunity_stage(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    opp_id = _uuid_or_none(args.get("opportunity_id"))
    opp_query = (args.get("opportunity_query") or "").strip()
    stage_query = (args.get("stage") or "").strip()
    if not stage_query:
        return {"error": "stage_required"}

    opp: Opportunity | None = None
    if opp_id is not None:
        opp = ctx.session.exec(
            select(Opportunity).where(
                Opportunity.id == opp_id,
                Opportunity.workspace_id == ctx.workspace_id,
                Opportunity.deleted_at.is_(None),
            )
        ).first()
    elif opp_query:
        like = f"%{like_escape(opp_query)}%"
        opp = ctx.session.exec(
            select(Opportunity)
            .where(
                Opportunity.workspace_id == ctx.workspace_id,
                Opportunity.deleted_at.is_(None),
                Opportunity.name.ilike(like, escape="\\"),
            )
            .order_by(Opportunity.amount.desc())
            .limit(1)
        ).first()
    if opp is None:
        return {"error": "opportunity_not_found"}

    stages = list(ctx.session.exec(
        select(PipelineStage).where(
            PipelineStage.workspace_id == ctx.workspace_id,
            PipelineStage.pipeline_id == opp.pipeline_id,
            PipelineStage.deleted_at.is_(None),
        )
    ).all())
    if not stages:
        return {"error": "pipeline_has_no_stages"}
    ql = stage_query.lower()
    target = next((s for s in stages if s.name.lower() == ql), None)
    if target is None:
        target = next((s for s in stages if ql in s.name.lower()), None)
    if target is None:
        return {"error": "stage_not_found", "available": [s.name for s in stages]}

    opp.stage_id = target.id
    if target.is_won:
        opp.status = OpportunityStatus.won
        opp.closed_at = datetime.now(timezone.utc)
        opp.probability = 100.0
    elif target.is_lost:
        opp.status = OpportunityStatus.lost
        opp.closed_at = datetime.now(timezone.utc)
        opp.probability = 0.0
    else:
        opp.probability = target.probability
    ctx.session.add(opp)
    ctx.session.commit()
    ctx.session.refresh(opp)
    return {
        "id": str(opp.id),
        "name": opp.name,
        "stage": target.name,
        "status": opp.status.value if hasattr(opp.status, "value") else str(opp.status),
    }


def _list_recent_activity(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(int(args.get("limit", 10)), 50)
    stmt = (
        select(Activity)
        .where(
            Activity.workspace_id == ctx.workspace_id,
            Activity.deleted_at.is_(None),
        )
        .order_by(Activity.occurred_at.desc())
        .limit(limit)
    )
    return {
        "results": [
            {
                "id": str(a.id),
                "kind": a.kind,
                "subject_type": a.subject_type,
                "subject_id": str(a.subject_id),
                "summary": a.summary,
                "occurred_at": a.occurred_at.isoformat(),
            }
            for a in ctx.session.exec(stmt).all()
        ]
    }


def _today_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    overdue = ctx.session.exec(
        select(Task).where(
            Task.workspace_id == ctx.workspace_id,
            Task.deleted_at.is_(None),
            Task.status.in_([TaskStatus.todo, TaskStatus.in_progress, TaskStatus.blocked]),
            Task.due_at.is_not(None),
            Task.due_at < now,
        )
    ).all()
    due_today = ctx.session.exec(
        select(Task).where(
            Task.workspace_id == ctx.workspace_id,
            Task.deleted_at.is_(None),
            Task.status.in_([TaskStatus.todo, TaskStatus.in_progress, TaskStatus.blocked]),
            Task.due_at.is_not(None),
            Task.due_at >= now,
            Task.due_at <= end_of_day,
        )
    ).all()
    meetings_today = ctx.session.exec(
        select(Meeting).where(
            Meeting.workspace_id == ctx.workspace_id,
            Meeting.deleted_at.is_(None),
            Meeting.starts_at >= start_of_day,
            Meeting.starts_at <= end_of_day,
        ).order_by(Meeting.starts_at.asc())
    ).all()
    return {
        "overdue_task_count": len(overdue),
        "tasks_due_today": [{"id": str(t.id), "title": t.title, "due_at": t.due_at.isoformat() if t.due_at else None} for t in due_today],
        "overdue_tasks": [{"id": str(t.id), "title": t.title, "due_at": t.due_at.isoformat() if t.due_at else None} for t in overdue[:10]],
        "meetings_today": [{"id": str(m.id), "title": m.title, "starts_at": m.starts_at.isoformat()} for m in meetings_today],
    }


def _save_preference(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    key = (args.get("key") or "").strip()
    value = (args.get("value") or "").strip()
    if not key or not value:
        return {"error": "key_and_value_required"}
    kind = (args.get("kind") or "preference").strip() or "preference"
    source = (args.get("source") or "user_told_me").strip() or "user_told_me"
    mem = JarvisMemory(
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        key=key,
        value=value,
        kind=kind,
        source=source,
    )
    ctx.session.add(mem)
    ctx.session.commit()
    ctx.session.refresh(mem)
    return {"id": str(mem.id), "key": mem.key, "value": mem.value, "kind": mem.kind}


def _list_preferences(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    stmt = (
        select(JarvisMemory)
        .where(
            JarvisMemory.workspace_id == ctx.workspace_id,
            JarvisMemory.user_id == ctx.user_id,
            JarvisMemory.deleted_at.is_(None),
        )
        .order_by(JarvisMemory.created_at.desc())
    )
    seen: dict[str, dict[str, Any]] = {}
    for m in ctx.session.exec(stmt).all():
        if m.key in seen:
            continue
        seen[m.key] = {"key": m.key, "value": m.value, "kind": m.kind}
    return {"results": list(seen.values())}


def _log_interaction(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    kind = (args.get("kind") or "").strip().lower()
    if kind not in {"call", "email", "meeting_note", "sms", "whatsapp", "chat"}:
        return {"error": "invalid_kind"}
    summary = (args.get("summary") or "").strip()
    contact_id = _uuid_or_none(args.get("contact_id"))
    contact_query = (args.get("contact_query") or "").strip()

    resolved_contact: Contact | None = None
    if contact_id is not None:
        resolved_contact = ctx.session.exec(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.workspace_id == ctx.workspace_id,
                Contact.deleted_at.is_(None),
            )
        ).first()
    elif contact_query:
        like = f"%{like_escape(contact_query)}%"
        resolved_contact = ctx.session.exec(
            select(Contact)
            .where(
                Contact.workspace_id == ctx.workspace_id,
                Contact.deleted_at.is_(None),
                or_(
                    Contact.first_name.ilike(like, escape="\\"),
                    Contact.last_name.ilike(like, escape="\\"),
                    Contact.email.ilike(like, escape="\\"),
                ),
            )
            .limit(1)
        ).first()

    if not resolved_contact and (contact_id or contact_query):
        return {"error": "contact_not_found"}

    subject_type = "contact" if resolved_contact else "workspace"
    subject_id = resolved_contact.id if resolved_contact else ctx.workspace_id
    activity = Activity(
        workspace_id=ctx.workspace_id,
        actor_user_id=ctx.user_id,
        kind=kind,
        subject_type=subject_type,
        subject_id=subject_id,
        summary=summary or None,
        occurred_at=datetime.now(timezone.utc),
    )
    ctx.session.add(activity)
    ctx.session.commit()
    ctx.session.refresh(activity)
    return {
        "id": str(activity.id),
        "kind": activity.kind,
        "subject_type": subject_type,
        "subject_id": str(subject_id),
        "summary": activity.summary,
    }


def _reschedule_meeting(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    meeting_id = _uuid_or_none(args.get("meeting_id"))
    query = (args.get("query") or "").strip()
    new_start = args.get("starts_at")
    if not new_start:
        return {"error": "starts_at_required"}
    try:
        new_start_dt = datetime.fromisoformat(new_start.replace("Z", "+00:00"))
    except ValueError:
        return {"error": "invalid_starts_at"}
    new_end = args.get("ends_at")
    new_end_dt: datetime | None = None
    if new_end:
        try:
            new_end_dt = datetime.fromisoformat(new_end.replace("Z", "+00:00"))
        except ValueError:
            return {"error": "invalid_ends_at"}
    # Normalize everything to tz-aware UTC. Without this, the meeting columns
    # come back naive on SQLite and aware on Postgres, and any mix with the
    # ISO-parsed `new_start_dt` (which is aware when the caller writes 'Z' or
    # '+00:00') would blow up the `meeting.ends_at <= meeting.starts_at` check
    # with a TypeError. `_as_aware` is a no-op on values that already have tz.
    if new_start_dt.tzinfo is None:
        new_start_dt = new_start_dt.replace(tzinfo=timezone.utc)
    if new_end_dt is not None and new_end_dt.tzinfo is None:
        new_end_dt = new_end_dt.replace(tzinfo=timezone.utc)

    meeting: Meeting | None = None
    if meeting_id is not None:
        meeting = ctx.session.exec(
            select(Meeting).where(
                Meeting.id == meeting_id,
                Meeting.workspace_id == ctx.workspace_id,
                Meeting.deleted_at.is_(None),
            )
        ).first()
    elif query:
        like = f"%{like_escape(query)}%"
        meeting = ctx.session.exec(
            select(Meeting)
            .where(
                Meeting.workspace_id == ctx.workspace_id,
                Meeting.deleted_at.is_(None),
                Meeting.title.ilike(like, escape="\\"),
            )
            .order_by(Meeting.starts_at.asc())
            .limit(1)
        ).first()
    if meeting is None:
        return {"error": "meeting_not_found"}

    # Preserve original duration if only starts_at was moved. Coerce loaded
    # columns to aware UTC so the arithmetic and comparison below are safe.
    old_start = _as_aware(meeting.starts_at)
    old_end = _as_aware(meeting.ends_at)
    duration = old_end - old_start
    meeting.starts_at = new_start_dt
    meeting.ends_at = new_end_dt if new_end_dt else new_start_dt + duration
    if meeting.ends_at <= meeting.starts_at:
        return {"error": "ends_before_start"}
    ctx.session.add(meeting)
    ctx.session.commit()
    ctx.session.refresh(meeting)
    return {
        "id": str(meeting.id),
        "title": meeting.title,
        "starts_at": meeting.starts_at.isoformat(),
        "ends_at": meeting.ends_at.isoformat(),
    }


def _list_contacts_by_company(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    company_id = _uuid_or_none(args.get("company_id"))
    query = (args.get("company_query") or "").strip()
    if company_id is None and query:
        like = f"%{like_escape(query)}%"
        company = ctx.session.exec(
            select(Company)
            .where(
                Company.workspace_id == ctx.workspace_id,
                Company.deleted_at.is_(None),
                or_(Company.name.ilike(like, escape="\\"), Company.domain.ilike(like, escape="\\")),
            )
            .limit(1)
        ).first()
        if company is None:
            return {"error": "company_not_found"}
        company_id = company.id
    if company_id is None:
        return {"error": "company_required"}
    stmt = (
        select(Contact)
        .where(
            Contact.workspace_id == ctx.workspace_id,
            Contact.deleted_at.is_(None),
            Contact.company_id == company_id,
        )
        .order_by(Contact.first_name.asc())
        .limit(min(int(args.get("limit", 25)), 100))
    )
    rows = ctx.session.exec(stmt).all()
    return {
        "company_id": str(company_id),
        "results": [
            {
                "id": str(c.id),
                "name": f"{c.first_name} {c.last_name or ''}".strip(),
                "email": c.email,
                "job_title": c.job_title,
            }
            for c in rows
        ],
    }


def _as_aware(dt):
    """Coerce a possibly-naive datetime (as SQLite hands us back) to UTC-aware.

    SQLAlchemy on SQLite stores datetimes as ISO strings but hands them back
    naive by default, so Python-side comparisons with `datetime.now(utc)` raise
    "can't compare offset-naive and offset-aware datetimes".
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _forecast(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Bucket open opportunities by expected_close_date × probability.

    Buckets (from `now`): overdue, this_week, this_month, next_month, later, no_date.
    """
    now = datetime.now(timezone.utc)
    # Anchor end_of_week to 23:59 of Sunday. Without this, on Sundays
    # `end_of_week == now` and every future close_date falls into next_month,
    # not this_week — caught by the flaky forecast test on tick 28.
    end_of_week = (now + timedelta(days=(6 - now.weekday()))).replace(
        hour=23, minute=59, second=59, microsecond=0,
    )
    # End of month: naive but correct enough — first day of next month minus 1s.
    if now.month == 12:
        first_next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        first_next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if first_next_month.month == 12:
        first_month_after = first_next_month.replace(year=first_next_month.year + 1, month=1, day=1)
    else:
        first_month_after = first_next_month.replace(month=first_next_month.month + 1, day=1)

    stmt = select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
    )
    buckets: dict[str, dict[str, float]] = {
        "overdue": {"count": 0, "amount": 0.0, "weighted": 0.0},
        "this_week": {"count": 0, "amount": 0.0, "weighted": 0.0},
        "this_month": {"count": 0, "amount": 0.0, "weighted": 0.0},
        "next_month": {"count": 0, "amount": 0.0, "weighted": 0.0},
        "later": {"count": 0, "amount": 0.0, "weighted": 0.0},
        "no_date": {"count": 0, "amount": 0.0, "weighted": 0.0},
    }
    for opp in ctx.session.exec(stmt).all():
        prob = opp.probability / 100.0 if opp.probability > 1 else opp.probability
        weighted = float(opp.amount) * prob
        close = _as_aware(opp.expected_close_date)
        if close is None:
            key = "no_date"
        elif close < now:
            key = "overdue"
        elif close <= end_of_week:
            key = "this_week"
        elif close < first_next_month:
            key = "this_month"
        elif close < first_month_after:
            key = "next_month"
        else:
            key = "later"
        buckets[key]["count"] += 1
        buckets[key]["amount"] += float(opp.amount)
        buckets[key]["weighted"] += weighted
    totals = {
        "count": sum(b["count"] for b in buckets.values()),
        "amount": sum(b["amount"] for b in buckets.values()),
        "weighted": sum(b["weighted"] for b in buckets.values()),
    }
    return {"buckets": buckets, "totals": totals, "as_of": now.isoformat()}


def _search_everywhere(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Unified ILIKE search across contacts/companies/leads/opportunities/notes.

    Deliberately backend-agnostic (works on SQLite + Postgres). If we later want
    ranking, swap the underlying query for SQLite FTS5 or Postgres tsvector —
    the tool contract stays the same.
    """
    query: str = (args.get("query") or "").strip()
    per_limit = min(int(args.get("limit_per_kind", 5)), 25)
    if not query:
        return {"results": {}, "total": 0}
    like = f"%{like_escape(query)}%"
    total = 0
    grouped: dict[str, list[dict[str, Any]]] = {}

    # Contacts
    stmt = select(Contact).where(
        Contact.workspace_id == ctx.workspace_id,
        Contact.deleted_at.is_(None),
        or_(
            Contact.first_name.ilike(like, escape="\\"),
            Contact.last_name.ilike(like, escape="\\"),
            Contact.email.ilike(like, escape="\\"),
            Contact.phone.ilike(like, escape="\\"),
            Contact.job_title.ilike(like, escape="\\"),
            Contact.notes.ilike(like, escape="\\"),
        ),
    ).limit(per_limit)
    grouped["contacts"] = [
        {
            "id": str(c.id),
            "name": f"{c.first_name} {c.last_name or ''}".strip(),
            "email": c.email,
            "job_title": c.job_title,
        }
        for c in ctx.session.exec(stmt).all()
    ]
    total += len(grouped["contacts"])

    # Companies
    stmt = select(Company).where(
        Company.workspace_id == ctx.workspace_id,
        Company.deleted_at.is_(None),
        or_(
            Company.name.ilike(like, escape="\\"),
            Company.domain.ilike(like, escape="\\"),
            Company.industry.ilike(like, escape="\\"),
            Company.description.ilike(like, escape="\\"),
        ),
    ).limit(per_limit)
    grouped["companies"] = [
        {"id": str(c.id), "name": c.name, "domain": c.domain, "industry": c.industry}
        for c in ctx.session.exec(stmt).all()
    ]
    total += len(grouped["companies"])

    # Leads
    stmt = select(Lead).where(
        Lead.workspace_id == ctx.workspace_id,
        Lead.deleted_at.is_(None),
        or_(
            Lead.first_name.ilike(like, escape="\\"),
            Lead.last_name.ilike(like, escape="\\"),
            Lead.email.ilike(like, escape="\\"),
            Lead.company_name.ilike(like, escape="\\"),
            Lead.notes.ilike(like, escape="\\"),
        ),
    ).limit(per_limit)
    grouped["leads"] = [
        {
            "id": str(l.id),
            "name": f"{l.first_name} {l.last_name or ''}".strip(),
            "company_name": l.company_name,
            "status": l.status.value if hasattr(l.status, "value") else str(l.status),
        }
        for l in ctx.session.exec(stmt).all()
    ]
    total += len(grouped["leads"])

    # Opportunities
    stmt = select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
        or_(
            Opportunity.name.ilike(like, escape="\\"),
            Opportunity.description.ilike(like, escape="\\"),
        ),
    ).limit(per_limit)
    grouped["opportunities"] = [
        {
            "id": str(o.id),
            "name": o.name,
            "amount": o.amount,
            "currency": o.currency,
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
        }
        for o in ctx.session.exec(stmt).all()
    ]
    total += len(grouped["opportunities"])

    # Notes (body text)
    stmt = select(Note).where(
        Note.workspace_id == ctx.workspace_id,
        Note.deleted_at.is_(None),
        Note.body.ilike(like, escape="\\"),
    ).limit(per_limit)
    grouped["notes"] = [
        {"id": str(n.id), "body_preview": (n.body[:120] + "…") if len(n.body) > 120 else n.body}
        for n in ctx.session.exec(stmt).all()
    ]
    total += len(grouped["notes"])

    return {"query": query, "results": grouped, "total": total}


def _week_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    end_of_week = now + timedelta(days=(6 - now.weekday()), hours=23 - now.hour,
                                  minutes=59 - now.minute, seconds=59 - now.second)

    open_opps = list(ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
            Opportunity.expected_close_date.is_not(None),
            Opportunity.expected_close_date <= end_of_week,
        )
    ).all())
    tasks_due = list(ctx.session.exec(
        select(Task).where(
            Task.workspace_id == ctx.workspace_id,
            Task.deleted_at.is_(None),
            Task.status.in_([TaskStatus.todo, TaskStatus.in_progress, TaskStatus.blocked]),
            Task.due_at.is_not(None),
            Task.due_at <= end_of_week,
        ).order_by(Task.due_at.asc())
    ).all())
    meetings = list(ctx.session.exec(
        select(Meeting).where(
            Meeting.workspace_id == ctx.workspace_id,
            Meeting.deleted_at.is_(None),
            Meeting.starts_at >= now,
            Meeting.starts_at <= end_of_week,
        ).order_by(Meeting.starts_at.asc())
    ).all())

    weighted = sum(o.amount * (o.probability / 100.0 if o.probability > 1 else o.probability) for o in open_opps)
    total_amount = sum(o.amount for o in open_opps)
    return {
        "week_ends_at": end_of_week.isoformat(),
        "opportunities_closing": [
            {"id": str(o.id), "name": o.name, "amount": o.amount, "currency": o.currency,
             "expected_close_date": o.expected_close_date.isoformat() if o.expected_close_date else None}
            for o in open_opps
        ],
        "tasks_due": [{"id": str(t.id), "title": t.title, "due_at": t.due_at.isoformat() if t.due_at else None} for t in tasks_due],
        "meetings": [{"id": str(m.id), "title": m.title, "starts_at": m.starts_at.isoformat()} for m in meetings],
        "weighted_pipeline": weighted,
        "total_pipeline": total_amount,
    }


def _recalculate_lead_scores(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.lead_scoring import recompute_all
    reset = bool(args.get("reset_to_zero", True))
    return recompute_all(ctx.session, ctx.workspace_id, reset_to_zero=reset)


def _list_activity_for_subject(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    subject_type = (args.get("subject_type") or "").strip().lower()
    subject_id = _uuid_or_none(args.get("subject_id"))
    if not subject_type or subject_id is None:
        return {"error": "subject_type_and_id_required"}
    limit = min(int(args.get("limit", 20)), 100)
    stmt = (
        select(Activity)
        .where(
            Activity.workspace_id == ctx.workspace_id,
            Activity.deleted_at.is_(None),
            Activity.subject_type == subject_type,
            Activity.subject_id == subject_id,
        )
        .order_by(Activity.occurred_at.desc())
        .limit(limit)
    )
    return {
        "results": [
            {
                "id": str(a.id),
                "kind": a.kind,
                "summary": a.summary,
                "occurred_at": a.occurred_at.isoformat(),
                "actor_user_id": str(a.actor_user_id) if a.actor_user_id else None,
            }
            for a in ctx.session.exec(stmt).all()
        ]
    }


def _tag_entity(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Tag a subject entity. Creates the tag if missing, resolves the subject by
    (subject_type + query) or explicit subject_id. Returns idempotently.
    """
    tag_name = (args.get("tag") or "").strip()
    if not tag_name:
        return {"error": "tag_required"}
    subject_type = (args.get("subject_type") or "").strip().lower()
    subject_id = _uuid_or_none(args.get("subject_id"))
    query = (args.get("query") or "").strip()

    if subject_id is None and subject_type and query:
        like = f"%{like_escape(query)}%"
        row = None
        if subject_type == "contact":
            row = ctx.session.exec(select(Contact).where(
                Contact.workspace_id == ctx.workspace_id,
                Contact.deleted_at.is_(None),
                or_(Contact.first_name.ilike(like, escape="\\"), Contact.last_name.ilike(like, escape="\\"), Contact.email.ilike(like, escape="\\")),
            ).limit(1)).first()
        elif subject_type == "company":
            row = ctx.session.exec(select(Company).where(
                Company.workspace_id == ctx.workspace_id,
                Company.deleted_at.is_(None),
                or_(Company.name.ilike(like, escape="\\"), Company.domain.ilike(like, escape="\\")),
            ).limit(1)).first()
        elif subject_type == "opportunity":
            row = ctx.session.exec(select(Opportunity).where(
                Opportunity.workspace_id == ctx.workspace_id,
                Opportunity.deleted_at.is_(None),
                Opportunity.name.ilike(like, escape="\\"),
            ).limit(1)).first()
        elif subject_type == "lead":
            row = ctx.session.exec(select(Lead).where(
                Lead.workspace_id == ctx.workspace_id,
                Lead.deleted_at.is_(None),
                or_(Lead.first_name.ilike(like, escape="\\"), Lead.last_name.ilike(like, escape="\\"), Lead.email.ilike(like, escape="\\")),
            ).limit(1)).first()
        if row is None:
            return {"error": "subject_not_found"}
        subject_id = row.id

    if subject_id is None or not subject_type:
        return {"error": "subject_required"}

    # Upsert tag by name.
    tag = ctx.session.exec(
        select(Tag).where(
            Tag.workspace_id == ctx.workspace_id,
            Tag.deleted_at.is_(None),
            Tag.name == tag_name,
        )
    ).first()
    if tag is None:
        tag = Tag(workspace_id=ctx.workspace_id, name=tag_name)
        ctx.session.add(tag)
        ctx.session.flush()

    # Attach if not already linked.
    link = ctx.session.exec(
        select(TagLink).where(
            TagLink.workspace_id == ctx.workspace_id,
            TagLink.deleted_at.is_(None),
            TagLink.tag_id == tag.id,
            TagLink.subject_type == subject_type,
            TagLink.subject_id == subject_id,
        )
    ).first()
    already = link is not None
    if not already:
        link = TagLink(
            workspace_id=ctx.workspace_id, tag_id=tag.id,
            subject_type=subject_type, subject_id=subject_id,
        )
        ctx.session.add(link)
    ctx.session.commit()
    return {
        "tag_id": str(tag.id),
        "tag_name": tag.name,
        "subject_type": subject_type,
        "subject_id": str(subject_id),
        "already_linked": already,
    }


def _uuid_or_none(v: Any) -> UUID | None:
    if v is None or v == "":
        return None
    if isinstance(v, UUID):
        return v
    try:
        return UUID(str(v))
    except ValueError:
        return None


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolSpec(
        name="search_contacts",
        description="Search contacts in the current workspace by name, email, phone, or job title.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text search term."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "required": ["query"],
        },
        handler=_search_contacts,
    ))
    reg.register(ToolSpec(
        name="list_open_opportunities",
        description="List open opportunities sorted by amount descending.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}},
        },
        handler=_list_open_opportunities,
    ))
    reg.register(ToolSpec(
        name="create_task",
        description="Create a task for the current user in the current workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "due_at": {"type": "string", "description": "ISO-8601 datetime with timezone."},
            },
            "required": ["title"],
        },
        handler=_create_task,
    ))
    reg.register(ToolSpec(
        name="summarize_pipeline",
        description="Return aggregate statistics for open opportunities.",
        input_schema={"type": "object", "properties": {}},
        handler=_summarize_pipeline,
    ))
    reg.register(ToolSpec(
        name="search_companies",
        description="Search companies in the current workspace by name, domain, or industry.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "required": ["query"],
        },
        handler=_search_companies,
    ))
    reg.register(ToolSpec(
        name="create_note",
        description="Create a note. Optionally attach to a contact, company, opportunity, or lead.",
        input_schema={
            "type": "object",
            "properties": {
                "body": {"type": "string"},
                "related_contact_id": {"type": "string"},
                "related_company_id": {"type": "string"},
                "related_opportunity_id": {"type": "string"},
                "related_lead_id": {"type": "string"},
            },
            "required": ["body"],
        },
        handler=_create_note,
    ))
    reg.register(ToolSpec(
        name="mark_task_done",
        description="Mark a task as done. Provide task_id or a query matching the task title.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "query": {"type": "string"},
            },
        },
        handler=_mark_task_done,
    ))
    reg.register(ToolSpec(
        name="move_opportunity_stage",
        description="Move an opportunity to a stage by name (e.g. 'Won', 'Negotiation'). Use opportunity_id or opportunity_query.",
        input_schema={
            "type": "object",
            "properties": {
                "opportunity_id": {"type": "string"},
                "opportunity_query": {"type": "string"},
                "stage": {"type": "string"},
            },
            "required": ["stage"],
        },
        handler=_move_opportunity_stage,
    ))
    reg.register(ToolSpec(
        name="list_recent_activity",
        description="Return the most recent activity timeline entries for the workspace.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}},
        },
        handler=_list_recent_activity,
    ))
    reg.register(ToolSpec(
        name="today_summary",
        description="Snapshot of tasks and meetings for today plus overdue tasks.",
        input_schema={"type": "object", "properties": {}},
        handler=_today_summary,
    ))
    reg.register(ToolSpec(
        name="save_preference",
        description="Persist a user preference or fact that Jarvis should remember on future turns.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
                "kind": {"type": "string", "enum": ["preference", "fact", "style", "routine"]},
                "source": {"type": "string"},
            },
            "required": ["key", "value"],
        },
        handler=_save_preference,
    ))
    reg.register(ToolSpec(
        name="list_preferences",
        description="List the current user's stored preferences (latest per key).",
        input_schema={"type": "object", "properties": {}},
        handler=_list_preferences,
    ))
    reg.register(ToolSpec(
        name="log_interaction",
        description="Log an interaction (call, email, sms, whatsapp, chat, meeting_note) with a contact.",
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["call", "email", "sms", "whatsapp", "chat", "meeting_note"]},
                "summary": {"type": "string"},
                "contact_id": {"type": "string"},
                "contact_query": {"type": "string"},
            },
            "required": ["kind"],
        },
        handler=_log_interaction,
    ))
    reg.register(ToolSpec(
        name="list_contacts_by_company",
        description="List contacts belonging to a company. Provide company_id or company_query.",
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "company_query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25},
            },
        },
        handler=_list_contacts_by_company,
    ))
    reg.register(ToolSpec(
        name="forecast",
        description="Bucket open opportunities by expected close date (overdue/this_week/this_month/next_month/later/no_date) with amount + weighted amount.",
        input_schema={"type": "object", "properties": {}},
        handler=_forecast,
    ))
    reg.register(ToolSpec(
        name="search_everywhere",
        description="Free-text search across contacts, companies, leads, opportunities, and notes in the workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit_per_kind": {"type": "integer", "minimum": 1, "maximum": 25, "default": 5},
            },
            "required": ["query"],
        },
        handler=_search_everywhere,
    ))
    reg.register(ToolSpec(
        name="tag_entity",
        description="Attach a named tag to a subject (contact/company/lead/opportunity). Creates the tag if missing.",
        input_schema={
            "type": "object",
            "properties": {
                "tag": {"type": "string"},
                "subject_type": {"type": "string", "enum": ["contact", "company", "lead", "opportunity"]},
                "subject_id": {"type": "string"},
                "query": {"type": "string"},
            },
            "required": ["tag", "subject_type"],
        },
        handler=_tag_entity,
    ))
    reg.register(ToolSpec(
        name="week_summary",
        description="Summarize the current week: opportunities closing this week, tasks due, meetings, and pipeline totals.",
        input_schema={"type": "object", "properties": {}},
        handler=_week_summary,
    ))
    reg.register(ToolSpec(
        name="recalculate_lead_scores",
        description="Recompute scores for every lead in the workspace using active scoring rules.",
        input_schema={
            "type": "object",
            "properties": {"reset_to_zero": {"type": "boolean", "default": True}},
        },
        handler=_recalculate_lead_scores,
    ))
    reg.register(ToolSpec(
        name="list_activity_for_subject",
        description="Activity timeline entries for a specific subject (contact/company/opportunity/lead/task/meeting).",
        input_schema={
            "type": "object",
            "properties": {
                "subject_type": {"type": "string"},
                "subject_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "required": ["subject_type", "subject_id"],
        },
        handler=_list_activity_for_subject,
    ))
    reg.register(ToolSpec(
        name="reschedule_meeting",
        description="Reschedule a meeting. Provide meeting_id or query, plus new starts_at (ISO-8601).",
        input_schema={
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
                "query": {"type": "string"},
                "starts_at": {"type": "string"},
                "ends_at": {"type": "string"},
            },
            "required": ["starts_at"],
        },
        handler=_reschedule_meeting,
    ))
    # Device-level tools (web/calendar/social/filesystem) — degrade gracefully.
    try:
        from app.jarvis.device_tools import register_device_tools
        register_device_tools(reg)
    except Exception:
        pass
    return reg
