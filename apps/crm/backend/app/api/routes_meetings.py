from datetime import datetime
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Contact, Meeting, Opportunity
from app.schemas.common import Page
from app.schemas.work import MeetingCreate, MeetingRead, MeetingUpdate
from app.services import crud
from app.services.activity_service import log_activity

router = APIRouter(prefix="/meetings", tags=["meetings"])


def _validate_window(starts_at: datetime, ends_at: datetime) -> None:
    if ends_at <= starts_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ends_at must be after starts_at")


def _validate_relations(session, workspace_id, data: dict) -> None:
    """Tenant-check the related_* FKs in a meeting payload."""
    if "related_contact_id" in data:
        crud.verify_scoped_exists(session, Contact, workspace_id, data["related_contact_id"], label="contact")
    if "related_opportunity_id" in data:
        crud.verify_scoped_exists(session, Opportunity, workspace_id, data["related_opportunity_id"], label="opportunity")


@router.post("", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
def create_meeting(
    payload: MeetingCreate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Meeting:
    _validate_window(payload.starts_at, payload.ends_at)
    data = payload.model_dump(exclude_unset=True)
    _validate_relations(session, ws.id, data)
    obj = Meeting(
        workspace_id=ws.id,
        organizer_user_id=user.id,
        **data,
    )
    obj = crud.create_scoped(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="created",
        subject_type="meeting",
        subject_id=obj.id,
        summary=obj.title,
    )
    return obj


@router.get("", response_model=Page[MeetingRead])
def list_meetings(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[MeetingRead]:
    base = crud.scoped_query(Meeting, ws.id)
    if since is not None:
        base = base.where(Meeting.starts_at >= since)
    if until is not None:
        base = base.where(Meeting.starts_at <= until)
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Meeting.starts_at.asc()).limit(limit).offset(offset)).all()
    return Page[MeetingRead].build([MeetingRead.model_validate(r) for r in rows], total, limit, offset)


@router.get("/{meeting_id}", response_model=MeetingRead)
def get_meeting(
    meeting_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> Meeting:
    return crud.get_or_404(session, Meeting, ws.id, meeting_id)


@router.patch("/{meeting_id}", response_model=MeetingRead)
def update_meeting(
    meeting_id: UUID,
    payload: MeetingUpdate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Meeting:
    obj = crud.get_or_404(session, Meeting, ws.id, meeting_id)
    data = payload.model_dump(exclude_unset=True)
    # A client sending `{"starts_at": null}` would leave new_start = None and
    # blow up _validate_window with a TypeError. Reject explicit-null on
    # required datetime fields early with a clean 400.
    if data.get("starts_at", ...) is None or data.get("ends_at", ...) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "starts_at and ends_at cannot be null")
    _validate_relations(session, ws.id, data)
    new_start = data.get("starts_at", obj.starts_at)
    new_end = data.get("ends_at", obj.ends_at)
    _validate_window(new_start, new_end)
    allowed = {
        "title", "description", "starts_at", "ends_at", "location", "video_url",
        "related_contact_id", "related_opportunity_id", "summary",
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
        subject_type="meeting",
        subject_id=obj.id,
        summary=obj.title,
    )
    return obj


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> None:
    obj = crud.get_or_404(session, Meeting, ws.id, meeting_id)
    crud.soft_delete(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="deleted",
        subject_type="meeting",
        subject_id=obj.id,
    )
