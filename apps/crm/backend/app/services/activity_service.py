"""Append-only activity timeline. Every mutation on a CRM object should call
`log_activity` so Jarvis and dashboards have a coherent history to reason over.
"""
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from sqlmodel import Session

from app.models import Activity


def log_activity(
    session: Session,
    *,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    kind: str,
    subject_type: str,
    subject_id: UUID,
    summary: str | None = None,
    data: dict[str, Any] | None = None,
    commit: bool = True,
) -> Activity:
    activity = Activity(
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        kind=kind,
        subject_type=subject_type,
        subject_id=subject_id,
        summary=summary,
        data=json.dumps(data, default=str) if data else None,
        occurred_at=datetime.now(timezone.utc),
    )
    session.add(activity)
    if commit:
        session.commit()
        session.refresh(activity)
        # Trigger workflows synchronously after the activity is committed. The
        # runtime has its own loop guard so activities generated *by* workflow
        # steps don't recurse. Imported lazily to avoid a circular import at
        # module load time.
        from app.services.workflow_service import evaluate_workflows_for_activity
        evaluate_workflows_for_activity(session, activity)
    return activity
