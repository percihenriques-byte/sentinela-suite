from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Company, Contact, Lead, Note, Opportunity
from app.schemas.common import Page
from app.schemas.work import NoteCreate, NoteRead, NoteUpdate
from app.services import crud
from app.services.activity_service import log_activity

router = APIRouter(prefix="/notes", tags=["notes"])


def _validate_relations(session, workspace_id, data: dict) -> None:
    """Tenant-check the related_* FKs in a note payload."""
    if "related_contact_id" in data:
        crud.verify_scoped_exists(session, Contact, workspace_id, data["related_contact_id"], label="contact")
    if "related_company_id" in data:
        crud.verify_scoped_exists(session, Company, workspace_id, data["related_company_id"], label="company")
    if "related_opportunity_id" in data:
        crud.verify_scoped_exists(session, Opportunity, workspace_id, data["related_opportunity_id"], label="opportunity")
    if "related_lead_id" in data:
        crud.verify_scoped_exists(session, Lead, workspace_id, data["related_lead_id"], label="lead")


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Note:
    data = payload.model_dump(exclude_unset=True)
    _validate_relations(session, ws.id, data)
    obj = Note(
        workspace_id=ws.id,
        author_user_id=user.id,
        **data,
    )
    obj = crud.create_scoped(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="note_added",
        subject_type="note",
        subject_id=obj.id,
    )
    return obj


@router.get("", response_model=Page[NoteRead])
def list_notes(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    contact_id: Annotated[UUID | None, Query()] = None,
    company_id: Annotated[UUID | None, Query()] = None,
    opportunity_id: Annotated[UUID | None, Query()] = None,
    lead_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[NoteRead]:
    base = crud.scoped_query(Note, ws.id)
    if contact_id is not None:
        base = base.where(Note.related_contact_id == contact_id)
    if company_id is not None:
        base = base.where(Note.related_company_id == company_id)
    if opportunity_id is not None:
        base = base.where(Note.related_opportunity_id == opportunity_id)
    if lead_id is not None:
        base = base.where(Note.related_lead_id == lead_id)
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Note.created_at.desc()).limit(limit).offset(offset)).all()
    return Page[NoteRead].build([NoteRead.model_validate(r) for r in rows], total, limit, offset)


@router.get("/{note_id}", response_model=NoteRead)
def get_note(
    note_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> Note:
    return crud.get_or_404(session, Note, ws.id, note_id)


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(
    note_id: UUID,
    payload: NoteUpdate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Note:
    obj = crud.get_or_404(session, Note, ws.id, note_id)
    data = payload.model_dump(exclude_unset=True)
    _validate_relations(session, ws.id, data)
    allowed = {"body", "related_contact_id", "related_company_id", "related_opportunity_id", "related_lead_id"}
    crud.apply_updates(obj, data, allowed=allowed)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="updated",
        subject_type="note",
        subject_id=obj.id,
    )
    return obj


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> None:
    obj = crud.get_or_404(session, Note, ws.id, note_id)
    crud.soft_delete(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="deleted",
        subject_type="note",
        subject_id=obj.id,
    )
