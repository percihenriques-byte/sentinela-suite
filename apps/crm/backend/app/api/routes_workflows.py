import json
from typing import Annotated, Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Workflow, WorkflowRun, WorkflowStep
from app.schemas.common import Page
from app.services import crud

router = APIRouter(prefix="/workflows", tags=["workflows"])

ALLOWED_STEP_KINDS = {"create_task", "add_note", "set_lead_status", "move_opportunity"}


class TriggerModel(BaseModel):
    kind: str = "*"
    subject_type: str = "*"
    conditions: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowStepIn(BaseModel):
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    order_index: int = 0
    is_active: bool = True


class WorkflowStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    order_index: int
    is_active: bool
    payload_json: str | None = None


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    is_active: bool = True
    trigger: TriggerModel
    steps: list[WorkflowStepIn] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    trigger: TriggerModel | None = None


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None = None
    is_active: bool
    trigger_json: str
    run_count: int
    steps: list[WorkflowStepRead] = []


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workflow_id: UUID
    triggering_activity_id: UUID | None = None
    status: str
    error: str | None = None
    output_json: str | None = None
    started_at: str
    finished_at: str | None = None


def _validate_step(step: WorkflowStepIn) -> None:
    if step.kind not in ALLOWED_STEP_KINDS:
        raise HTTPException(400, f"unknown step kind: {step.kind}. Allowed: {sorted(ALLOWED_STEP_KINDS)}")


def _hydrate(session, ws_id, workflow: Workflow) -> WorkflowRead:
    steps_stmt = crud.scoped_query(WorkflowStep, ws_id).where(WorkflowStep.workflow_id == workflow.id).order_by(
        WorkflowStep.order_index.asc(), WorkflowStep.created_at.asc()
    )
    steps = list(session.exec(steps_stmt).all())
    return WorkflowRead(
        id=workflow.id, name=workflow.name, description=workflow.description,
        is_active=workflow.is_active, trigger_json=workflow.trigger_json,
        run_count=workflow.run_count,
        steps=[WorkflowStepRead.model_validate(s) for s in steps],
    )


WORKFLOW_TEMPLATES = {
    "hot_lead_task": {
        "name": "Follow-up automático em lead quente",
        "description": "Cria tarefa de follow-up quando um lead tem score >= 50",
        "trigger": {
            "kind": "created", "subject_type": "lead",
            "conditions": [{"field": "subject.score", "op": "gte", "value": "50"}],
        },
        "steps": [
            {"kind": "create_task", "payload": {
                "title": "Follow-up com lead {{subject_id}}",
                "due_in_days": 1, "priority": "high",
            }},
        ],
    },
    "opp_won_note": {
        "name": "Nota comemorativa em Won",
        "description": "Adiciona uma nota quando uma oportunidade é marcada como Won",
        "trigger": {
            "kind": "won", "subject_type": "opportunity",
            "conditions": [],
        },
        "steps": [
            {"kind": "add_note", "payload": {
                "body": "🏆 Oportunidade fechada! Enviar cesta / obrigado — ver playbook interno.",
            }},
        ],
    },
    "stale_lead_qualify": {
        "name": "Auto-qualificar leads por domínio corporativo",
        "description": "Marca lead como qualified se email não é gmail/hotmail/etc",
        "trigger": {
            "kind": "created", "subject_type": "lead",
            "conditions": [
                {"field": "subject.email_domain", "op": "not_in", "value": "gmail.com,hotmail.com,yahoo.com,outlook.com"}
            ],
        },
        "steps": [
            {"kind": "set_lead_status", "payload": {"status": "qualified"}},
        ],
    },
    "new_opp_task": {
        "name": "Ligar após criar oportunidade",
        "description": "Cria tarefa 'ligar' 2 dias após uma oportunidade ser criada",
        "trigger": {"kind": "created", "subject_type": "opportunity", "conditions": []},
        "steps": [
            {"kind": "create_task", "payload": {
                "title": "Ligar para discutir {{subject_id}}",
                "due_in_days": 2, "priority": "normal",
            }},
        ],
    },
}


@router.get("/templates")
def list_workflow_templates() -> dict:
    return {"templates": [{"key": k, **v} for k, v in WORKFLOW_TEMPLATES.items()]}


@router.post("/from-template/{template_key}", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
def create_workflow_from_template(
    template_key: str,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> WorkflowRead:
    tpl = WORKFLOW_TEMPLATES.get(template_key)
    if not tpl:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"template '{template_key}' not found")
    wf = Workflow(
        workspace_id=ws.id, name=tpl["name"], description=tpl["description"],
        is_active=True, trigger_json=json.dumps(tpl["trigger"]),
    )
    session.add(wf)
    session.flush()
    for i, s in enumerate(tpl["steps"]):
        session.add(WorkflowStep(
            workspace_id=ws.id, workflow_id=wf.id, kind=s["kind"],
            payload_json=json.dumps(s["payload"]), order_index=i, is_active=True,
        ))
    session.commit()
    session.refresh(wf)
    return _hydrate(session, ws.id, wf)


@router.post("", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate, session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> WorkflowRead:
    for s in payload.steps:
        _validate_step(s)
    wf = Workflow(
        workspace_id=ws.id, name=payload.name, description=payload.description,
        is_active=payload.is_active,
        trigger_json=json.dumps(payload.trigger.model_dump()),
    )
    session.add(wf)
    session.flush()
    for i, s in enumerate(payload.steps):
        session.add(WorkflowStep(
            workspace_id=ws.id, workflow_id=wf.id, kind=s.kind,
            payload_json=json.dumps(s.payload), order_index=s.order_index or i,
            is_active=s.is_active,
        ))
    session.commit()
    session.refresh(wf)
    return _hydrate(session, ws.id, wf)


@router.get("", response_model=Page[WorkflowRead])
def list_workflows(session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace,
                   limit: Annotated[int, Query(ge=1, le=200)] = 50,
                   offset: Annotated[int, Query(ge=0)] = 0) -> Page[WorkflowRead]:
    base = crud.scoped_query(Workflow, ws.id)
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Workflow.created_at.desc()).limit(limit).offset(offset)).all()
    return Page[WorkflowRead].build([_hydrate(session, ws.id, w) for w in rows], total, limit, offset)


@router.patch("/{workflow_id}", response_model=WorkflowRead)
def update_workflow(workflow_id: UUID, payload: WorkflowUpdate, session: SessionDep,
                    _user: CurrentUser, ws: CurrentWorkspace) -> WorkflowRead:
    wf = crud.get_or_404(session, Workflow, ws.id, workflow_id)
    data = payload.model_dump(exclude_unset=True)
    if "trigger" in data and data["trigger"] is not None:
        wf.trigger_json = json.dumps(data.pop("trigger"))
    crud.apply_updates(wf, data, allowed={"name", "description", "is_active"})
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return _hydrate(session, ws.id, wf)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(workflow_id: UUID, session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> None:
    wf = crud.get_or_404(session, Workflow, ws.id, workflow_id)
    crud.soft_delete(session, wf)


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunRead])
def list_workflow_runs(workflow_id: UUID, session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace,
                       limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[WorkflowRunRead]:
    crud.get_or_404(session, Workflow, ws.id, workflow_id)
    stmt = crud.scoped_query(WorkflowRun, ws.id).where(WorkflowRun.workflow_id == workflow_id).order_by(WorkflowRun.started_at.desc()).limit(limit)
    rows = session.exec(stmt).all()
    return [
        WorkflowRunRead(
            id=r.id, workflow_id=r.workflow_id,
            triggering_activity_id=r.triggering_activity_id,
            status=r.status, error=r.error, output_json=r.output_json,
            started_at=r.started_at.isoformat(),
            finished_at=r.finished_at.isoformat() if r.finished_at else None,
        )
        for r in rows
    ]
