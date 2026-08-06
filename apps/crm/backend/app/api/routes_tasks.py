from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Company, Contact, Lead, Opportunity, Task, TaskPriority, TaskStatus
from app.schemas.common import Page
from app.schemas.work import TaskCreate, TaskRead, TaskUpdate
from app.services import crud
from app.services.activity_service import log_activity

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _coerce_enum(cls, value, field_name):
    if value is None:
        return None
    try:
        return cls(value)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown {field_name}") from None


def _validate_relations(session, workspace_id, data: dict) -> None:
    """Tenant-check the related_* FKs in a task payload."""
    if "related_contact_id" in data:
        crud.verify_scoped_exists(session, Contact, workspace_id, data["related_contact_id"], label="contact")
    if "related_company_id" in data:
        crud.verify_scoped_exists(session, Company, workspace_id, data["related_company_id"], label="company")
    if "related_opportunity_id" in data:
        crud.verify_scoped_exists(session, Opportunity, workspace_id, data["related_opportunity_id"], label="opportunity")
    if "related_lead_id" in data:
        crud.verify_scoped_exists(session, Lead, workspace_id, data["related_lead_id"], label="lead")


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Task:
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        data["status"] = _coerce_enum(TaskStatus, data["status"], "task status")
    if "priority" in data:
        data["priority"] = _coerce_enum(TaskPriority, data["priority"], "task priority")
    _validate_relations(session, ws.id, data)
    if data.get("assignee_user_id") is None:
        data["assignee_user_id"] = user.id
    obj = Task(workspace_id=ws.id, **data)
    obj = crud.create_scoped(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="created",
        subject_type="task",
        subject_id=obj.id,
        summary=obj.title,
    )
    return obj


@router.get("", response_model=Page[TaskRead])
def list_tasks(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    assignee: Annotated[UUID | None, Query()] = None,
    due_before: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TaskRead]:
    base = crud.scoped_query(Task, ws.id)
    if status_filter:
        base = base.where(Task.status == _coerce_enum(TaskStatus, status_filter, "task status"))
    if assignee is not None:
        base = base.where(Task.assignee_user_id == assignee)
    if due_before is not None:
        base = base.where(Task.due_at.is_not(None)).where(Task.due_at < due_before)
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc()).limit(limit).offset(offset)).all()
    return Page[TaskRead].build([TaskRead.model_validate(r) for r in rows], total, limit, offset)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> Task:
    return crud.get_or_404(session, Task, ws.id, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Task:
    obj = crud.get_or_404(session, Task, ws.id, task_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        data["status"] = _coerce_enum(TaskStatus, data["status"], "task status")
    if "priority" in data:
        data["priority"] = _coerce_enum(TaskPriority, data["priority"], "task priority")
    _validate_relations(session, ws.id, data)
    # If moving to done and no completed_at yet, stamp it.
    if data.get("status") == TaskStatus.done and obj.completed_at is None:
        obj.completed_at = datetime.now(timezone.utc)
    allowed = {
        "title", "description", "status", "priority", "due_at", "assignee_user_id",
        "related_contact_id", "related_company_id", "related_opportunity_id", "related_lead_id",
    }
    crud.apply_updates(obj, data, allowed=allowed)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="updated",
        subject_type="task",
        subject_id=obj.id,
        summary=obj.title,
    )
    return obj


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> None:
    obj = crud.get_or_404(session, Task, ws.id, task_id)
    crud.soft_delete(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="deleted",
        subject_type="task",
        subject_id=obj.id,
    )
