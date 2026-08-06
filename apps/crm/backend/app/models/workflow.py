from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import Field

from app.models.base import WorkspaceScopedModel


class Workflow(WorkspaceScopedModel, table=True):
    """A named automation: when a triggering event matches, run the ordered steps.

    Trigger definition is kept as JSON-in-a-string to avoid a table sprawl at
    this stage. Example:
        {"kind": "created", "subject_type": "lead", "conditions": [
            {"field": "score", "op": "gte", "value": "50"}
        ]}
    """
    name: str = Field(nullable=False)
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    trigger_json: str = Field(nullable=False)  # see docstring
    run_count: int = Field(default=0)
    last_run_at: Optional[datetime] = None


class WorkflowStep(WorkspaceScopedModel, table=True):
    """One action inside a workflow.

    Kind + payload_json define what happens. Example kinds:
        create_task           payload: {"title_template": "Follow up with {subject}", "due_in_days": 2}
        add_note              payload: {"body_template": "..."}
        set_lead_status       payload: {"status": "qualified"}
        move_opportunity      payload: {"stage_name": "Negotiation"}
        webhook               payload: {"url": "https://..."}       # future
    """
    workflow_id: UUID = Field(foreign_key="workflow.id", index=True, nullable=False)
    order_index: int = Field(default=0)
    kind: str = Field(nullable=False)
    payload_json: Optional[str] = None
    is_active: bool = Field(default=True)


class WorkflowRun(WorkspaceScopedModel, table=True):
    """Audit trail — one row per triggered workflow execution."""
    workflow_id: UUID = Field(foreign_key="workflow.id", index=True, nullable=False)
    triggering_activity_id: Optional[UUID] = Field(default=None, foreign_key="activity.id", index=True)
    status: str = Field(default="succeeded", index=True)  # succeeded | failed | skipped
    error: Optional[str] = None
    started_at: datetime = Field(nullable=False)
    finished_at: Optional[datetime] = None
    output_json: Optional[str] = None  # summary of what was created/changed
