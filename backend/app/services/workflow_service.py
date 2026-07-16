"""Workflow runtime.

Synchronous, no queues. Runs immediately after `log_activity` commits, so
the entire causal chain is visible in one request.

Trigger JSON shape (workflow.trigger_json):
    {
        "kind": "created",            # matched literally (or "*" for any)
        "subject_type": "lead",       # matched literally (or "*" for any)
        "conditions": [                # optional list; ALL must match
            {"field": "score", "op": "gte", "value": "50"}
        ]
    }

Step kinds (workflow_step.kind + payload_json):
    create_task           {"title": "Follow up with {{subject_id}}", "due_in_days": 2, "priority": "high"}
    add_note              {"body": "Auto-note text"}
    set_lead_status       {"status": "qualified"}
    move_opportunity      {"stage_name": "Negotiation"}

`{{...}}` in string templates is expanded from the triggering activity's context
(subject_id, subject_type, kind, actor_user_id).

Loop guard: activities produced by workflow steps are marked with kind prefixed
`workflow.` (e.g. `workflow.created`) so they don't retrigger. Additionally we
never re-enter workflow evaluation while already inside it (thread-local flag).
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.models import (
    Activity,
    Contact,
    Lead,
    Note,
    Opportunity,
    OpportunityStatus,
    PipelineStage,
    Task,
    TaskPriority,
    TaskStatus,
    Workflow,
    WorkflowRun,
    WorkflowStep,
    LeadStatus,
)


logger = logging.getLogger("jarvis.workflow")
_local = threading.local()


def _entered() -> bool:
    return getattr(_local, "in_workflow", False)


def _enter() -> None:
    _local.in_workflow = True


def _leave() -> None:
    _local.in_workflow = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


_TPL_TOKEN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _substitute(template: str, ctx: dict[str, Any]) -> str:
    """Replace `{{key}}` (with optional surrounding whitespace) using ctx.

    Unknown keys are left as-is so the author notices the typo instead of
    getting silently-blank output. Previously only the literal `{{key}}` form
    matched, so `{{ subject_id }}` in a workflow step would render verbatim.
    """
    def _replace(m: "re.Match") -> str:
        key = m.group(1)
        return str(ctx[key]) if key in ctx else m.group(0)
    return _TPL_TOKEN.sub(_replace, template)


# ---- Condition matching ----------------------------------------------------

def _match_condition(cond: dict[str, Any], activity: Activity, session: Session) -> bool:
    field = cond.get("field", "")
    op = cond.get("op", "equals")
    expected = cond.get("value")

    # Activity-level fields
    if field in ("kind", "subject_type", "subject_id", "actor_user_id"):
        actual: Any = getattr(activity, field, None)
        actual = str(actual) if actual is not None else None
    # Subject-level fields — join to the referenced entity
    elif "." in field:
        head, tail = field.split(".", 1)
        if head != "subject":
            return False
        subj = _load_subject(session, activity)
        if subj is None:
            return False
        actual = _extract_subject_field(subj, tail)
    else:
        return False

    from app.services.lead_scoring import _match as scoring_match  # reuse the same op impl
    return scoring_match(op, actual, expected)


_SUBJECT_MODELS: dict[str, Any] = {
    "lead": Lead,
    "contact": Contact,
    "opportunity": Opportunity,
}


def _load_subject(session: Session, activity: Activity) -> Any | None:
    model = _SUBJECT_MODELS.get(activity.subject_type)
    if model is None:
        return None
    return session.get(model, activity.subject_id)


def _extract_subject_field(subj: Any, field: str) -> Any:
    if field == "score" and isinstance(subj, Lead):
        return subj.score
    if field == "email_domain" and isinstance(subj, Lead) and subj.email and "@" in subj.email:
        return subj.email.rsplit("@", 1)[-1].lower()
    if field == "status" and hasattr(subj, "status"):
        v = subj.status
        return v.value if hasattr(v, "value") else str(v)
    return getattr(subj, field, None)


def _trigger_matches(trigger: dict[str, Any], activity: Activity, session: Session) -> bool:
    kind = trigger.get("kind", "*")
    if kind != "*" and kind != activity.kind:
        return False
    subject_type = trigger.get("subject_type", "*")
    if subject_type != "*" and subject_type != activity.subject_type:
        return False
    for cond in trigger.get("conditions", []) or []:
        if not _match_condition(cond, activity, session):
            return False
    return True


# ---- Step execution --------------------------------------------------------

def _run_step(
    step: WorkflowStep,
    activity: Activity,
    session: Session,
    outputs: list[dict[str, Any]],
) -> None:
    payload = json.loads(step.payload_json) if step.payload_json else {}
    ctx = {
        "kind": activity.kind,
        "subject_type": activity.subject_type,
        "subject_id": str(activity.subject_id),
        "actor_user_id": str(activity.actor_user_id) if activity.actor_user_id else "",
    }
    kind = step.kind
    if kind == "create_task":
        title = _substitute(str(payload.get("title", "Follow-up")), ctx)
        due_in_days = int(payload.get("due_in_days", 1))
        priority = payload.get("priority", "normal")
        try:
            prio = TaskPriority(priority)
        except ValueError:
            prio = TaskPriority.normal
        task = Task(
            workspace_id=activity.workspace_id,
            title=title,
            priority=prio,
            due_at=_now() + timedelta(days=due_in_days),
            assignee_user_id=activity.actor_user_id,
            related_contact_id=activity.subject_id if activity.subject_type == "contact" else None,
            related_company_id=activity.subject_id if activity.subject_type == "company" else None,
            related_opportunity_id=activity.subject_id if activity.subject_type == "opportunity" else None,
            related_lead_id=activity.subject_id if activity.subject_type == "lead" else None,
        )
        session.add(task)
        session.flush()
        outputs.append({"kind": "task_created", "id": str(task.id), "title": task.title})
    elif kind == "add_note":
        body = _substitute(str(payload.get("body", "")), ctx)
        if not body:
            return
        note = Note(
            workspace_id=activity.workspace_id,
            body=body,
            author_user_id=activity.actor_user_id,
            related_contact_id=activity.subject_id if activity.subject_type == "contact" else None,
            related_company_id=activity.subject_id if activity.subject_type == "company" else None,
            related_opportunity_id=activity.subject_id if activity.subject_type == "opportunity" else None,
            related_lead_id=activity.subject_id if activity.subject_type == "lead" else None,
        )
        session.add(note)
        session.flush()
        outputs.append({"kind": "note_created", "id": str(note.id)})
    elif kind == "set_lead_status":
        if activity.subject_type != "lead":
            return
        lead = session.get(Lead, activity.subject_id)
        if lead is None:
            return
        try:
            lead.status = LeadStatus(payload.get("status", "new"))
        except ValueError:
            # Author typo — surface it so they can fix rather than watching a
            # workflow silently no-op forever.
            logger.warning(
                "workflow_set_lead_status_invalid lead_id=%s value=%r",
                lead.id, payload.get("status"),
            )
            return
        session.add(lead)
        outputs.append({"kind": "lead_status_set", "id": str(lead.id), "status": lead.status.value})
    elif kind == "move_opportunity":
        if activity.subject_type != "opportunity":
            return
        opp = session.get(Opportunity, activity.subject_id)
        if opp is None:
            return
        target_name = str(payload.get("stage_name", "")).strip().lower()
        if not target_name:
            return
        stages = list(session.exec(
            select(PipelineStage).where(
                PipelineStage.workspace_id == activity.workspace_id,
                PipelineStage.pipeline_id == opp.pipeline_id,
                PipelineStage.deleted_at.is_(None),
            )
        ).all())
        target = next((s for s in stages if s.name.lower() == target_name), None)
        if target is None:
            # Log so a misspelled stage name in a workflow (e.g. "negociation")
            # doesn't fail silently — was invisible before this change.
            logger.warning(
                "workflow_move_opportunity_stage_missing opp_id=%s target=%r available=%s",
                opp.id, target_name, [s.name for s in stages],
            )
            return
        opp.stage_id = target.id
        if target.is_won:
            opp.status = OpportunityStatus.won
            opp.closed_at = _now()
            opp.probability = 100.0
        elif target.is_lost:
            opp.status = OpportunityStatus.lost
            opp.closed_at = _now()
            opp.probability = 0.0
        else:
            opp.probability = target.probability
        session.add(opp)
        outputs.append({"kind": "opportunity_moved", "id": str(opp.id), "stage": target.name})


# ---- Public API ------------------------------------------------------------

def evaluate_workflows_for_activity(session: Session, activity: Activity) -> list[UUID]:
    """Run every matching workflow for a just-inserted Activity.

    Returns the list of WorkflowRun ids created. Silent on errors — each
    workflow is isolated and failures are logged + persisted on WorkflowRun.
    """
    if _entered():
        return []  # loop guard: workflow step wrote another activity — don't re-trigger
    if activity.kind.startswith("workflow."):
        return []

    workflows = list(session.exec(
        select(Workflow).where(
            Workflow.workspace_id == activity.workspace_id,
            Workflow.deleted_at.is_(None),
            Workflow.is_active.is_(True),
        )
    ).all())
    if not workflows:
        return []

    run_ids: list[UUID] = []
    _enter()
    try:
        for wf in workflows:
            try:
                trigger = json.loads(wf.trigger_json) if wf.trigger_json else {}
            except json.JSONDecodeError:
                # Corrupted trigger — log at WARNING so operators notice a
                # workflow silently doing nothing after a manual DB edit.
                logger.warning(
                    "workflow_trigger_json_invalid workflow_id=%s name=%s",
                    wf.id, wf.name,
                )
                continue
            if not _trigger_matches(trigger, activity, session):
                continue
            run = WorkflowRun(
                workspace_id=wf.workspace_id,
                workflow_id=wf.id,
                triggering_activity_id=activity.id,
                status="succeeded",
                started_at=_now(),
            )
            session.add(run)
            session.flush()
            outputs: list[dict[str, Any]] = []
            try:
                steps = list(session.exec(
                    select(WorkflowStep).where(
                        WorkflowStep.workspace_id == wf.workspace_id,
                        WorkflowStep.workflow_id == wf.id,
                        WorkflowStep.deleted_at.is_(None),
                        WorkflowStep.is_active.is_(True),
                    ).order_by(
                        WorkflowStep.order_index.asc(),
                        # Secondary sort by insert order so multiple steps with
                        # the same order_index (common when authors leave the
                        # default 0) run in a stable, predictable sequence.
                        WorkflowStep.created_at.asc(),
                    )
                ).all())
                for step in steps:
                    _run_step(step, activity, session, outputs)
            except Exception as e:
                run.status = "failed"
                run.error = str(e)[:500]
                logger.exception("workflow_step_failed workflow=%s", wf.id)
            run.finished_at = _now()
            run.output_json = json.dumps(outputs)
            wf.run_count = (wf.run_count or 0) + 1
            wf.last_run_at = run.finished_at
            session.add(wf)
            session.add(run)
            session.commit()
            run_ids.append(run.id)
    finally:
        _leave()
    return run_ids
