"""Seed a workspace with a realistic sample dataset — good for demos + onboarding.

Idempotent guard: refuses to seed a workspace that already contains data unless
`force=True`. Uses existing service layers so all activity logging + pipeline
bootstrap happen naturally.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.models import (
    Company,
    Contact,
    Lead,
    Meeting,
    Note,
    Opportunity,
    Task,
    TaskPriority,
)
from app.services import pipeline_service
from app.services.activity_service import log_activity


COMPANIES = [
    ("Nebula Labs", "nebula.io", "AI", "51-200"),
    ("Acme Corp", "acme.com", "Manufacturing", "1000+"),
    ("Widgets Inc", "widgets.co", "SaaS", "11-50"),
    ("Globex Ltd", "globex.co.uk", "Consulting", "201-500"),
    ("Initech", "initech.dev", "Fintech", "51-200"),
]

CONTACTS = [
    ("Ada",   "Byte",      "ada@nebula.io",       "CTO",           0),
    ("Grace", "Hop",       "grace@nebula.io",     "VP Engineering", 0),
    ("Linus", "Kernel",    "linus@acme.com",      "Head of Ops",   1),
    ("Ken",   "Threading", "ken@widgets.co",      "CEO",           2),
    ("Rob",   "Pike",      "rob@widgets.co",      "CTO",           2),
    ("Doug",  "Emacs",     "doug@globex.co.uk",   "Partner",       3),
    ("Barbara","Liskov",   "barbara@initech.dev", "CFO",           4),
    ("Alan",  "Turing",    "alan@initech.dev",    "Lead Data",     4),
]

LEADS = [
    ("Priya",  "Sharma",   "priya@enterprise.com",  "Enterprise Co",     "web",       "new",       35),
    ("Marcus", "Silva",    "marcus@gmail.com",      "Silva Consulting",  "referral",  "contacted", 60),
    ("Yuki",   "Tanaka",   "yuki@stellar.jp",       "Stellar Group",     "linkedin",  "qualified", 82),
]

OPPS = [
    ("Nebula Platform",     "Nebula Labs", "Ada",     45_000, 0, "USD"),
    ("Acme automation",     "Acme Corp",   "Linus",   120_000, 1, "USD"),
    ("Widgets integration", "Widgets Inc", "Ken",     18_000, 2, "USD"),
    ("Globex retainer",     "Globex Ltd",  "Doug",    30_000, 3, "GBP"),
    ("Initech treasury",    "Initech",     "Barbara", 260_000, 3, "USD"),
]

NOTES = [
    ("Initial discovery call — pain points around data quality.", "Nebula Platform"),
    ("Sent proposal v2 with tiered pricing.", "Acme automation"),
    ("Legal reviewing MSA. Blocker: liability cap.", "Initech treasury"),
]


def _workspace_is_empty(session: Session, workspace_id: UUID) -> bool:
    for m in (Company, Contact, Lead, Opportunity, Task, Meeting, Note):
        row = session.exec(
            select(m).where(m.workspace_id == workspace_id, m.deleted_at.is_(None)).limit(1)
        ).first()
        if row is not None:
            return False
    return True


def seed_workspace(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID,
    force: bool = False,
) -> dict[str, Any]:
    if not force and not _workspace_is_empty(session, workspace_id):
        return {"status": "skipped", "reason": "workspace_not_empty"}

    pipeline = pipeline_service.get_default_pipeline(session, workspace_id)
    stages = pipeline_service.get_stages(session, workspace_id, pipeline.id)
    now = datetime.now(timezone.utc)
    rand = random.Random(42)

    companies: list[Company] = []
    for name, domain, industry, size in COMPANIES:
        c = Company(
            workspace_id=workspace_id, name=name, domain=domain,
            industry=industry, size=size, owner_user_id=actor_user_id,
        )
        session.add(c)
        session.flush()
        companies.append(c)
        log_activity(session, workspace_id=workspace_id, actor_user_id=actor_user_id,
                     kind="created", subject_type="company", subject_id=c.id, summary=name, commit=False)

    contacts_by_name: dict[str, Contact] = {}
    for first, last, email, title, company_ix in CONTACTS:
        ct = Contact(
            workspace_id=workspace_id, first_name=first, last_name=last, email=email,
            job_title=title, company_id=companies[company_ix].id, owner_user_id=actor_user_id,
        )
        session.add(ct)
        session.flush()
        contacts_by_name[first] = ct
        log_activity(session, workspace_id=workspace_id, actor_user_id=actor_user_id,
                     kind="created", subject_type="contact", subject_id=ct.id,
                     summary=f"{first} {last}", commit=False)

    for first, last, email, company_name, source, status_val, score in LEADS:
        try:
            from app.models import LeadStatus
            status_enum = LeadStatus(status_val)
        except Exception:
            status_enum = None
        ld = Lead(
            workspace_id=workspace_id, first_name=first, last_name=last, email=email,
            company_name=company_name, source=source, score=score,
            owner_user_id=actor_user_id, **({"status": status_enum} if status_enum else {}),
        )
        session.add(ld)
        session.flush()
        log_activity(session, workspace_id=workspace_id, actor_user_id=actor_user_id,
                     kind="created", subject_type="lead", subject_id=ld.id,
                     summary=f"{first} {last}", commit=False)

    company_by_name = {c.name: c for c in companies}
    opps: list[Opportunity] = []
    for name, company_name, primary_contact, amount, stage_ix, currency in OPPS:
        stage = stages[min(stage_ix, len(stages) - 1)]
        opp = Opportunity(
            workspace_id=workspace_id, name=name,
            company_id=company_by_name.get(company_name).id if company_by_name.get(company_name) else None,
            contact_id=contacts_by_name.get(primary_contact).id if contacts_by_name.get(primary_contact) else None,
            pipeline_id=pipeline.id, stage_id=stage.id, amount=float(amount),
            currency=currency, probability=stage.probability,
            expected_close_date=now + timedelta(days=rand.randint(5, 60)),
            owner_user_id=actor_user_id,
        )
        session.add(opp)
        session.flush()
        opps.append(opp)
        log_activity(session, workspace_id=workspace_id, actor_user_id=actor_user_id,
                     kind="created", subject_type="opportunity", subject_id=opp.id,
                     summary=name, commit=False)

    opp_by_name = {o.name: o for o in opps}
    for body, opp_name in NOTES:
        note = Note(
            workspace_id=workspace_id, body=body, author_user_id=actor_user_id,
            related_opportunity_id=opp_by_name.get(opp_name).id if opp_by_name.get(opp_name) else None,
        )
        session.add(note)

    for i, title in enumerate(("Prep pitch deck", "Follow up with Ada", "Send updated pricing")):
        t = Task(
            workspace_id=workspace_id, title=title,
            priority=TaskPriority.high if i == 0 else TaskPriority.normal,
            due_at=now + timedelta(days=i + 1),
            assignee_user_id=actor_user_id,
        )
        session.add(t)

    m = Meeting(
        workspace_id=workspace_id, title="Nebula weekly sync",
        starts_at=now + timedelta(hours=24), ends_at=now + timedelta(hours=25),
        organizer_user_id=actor_user_id,
        related_contact_id=contacts_by_name["Ada"].id,
    )
    session.add(m)

    session.commit()
    return {
        "status": "ok",
        "counts": {
            "companies": len(COMPANIES),
            "contacts": len(CONTACTS),
            "leads": len(LEADS),
            "opportunities": len(OPPS),
            "notes": len(NOTES),
            "tasks": 3,
            "meetings": 1,
        },
    }
