from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Lead, LeadStatus
from app.schemas.common import Page
from app.schemas.crm import (
    LeadConvertRequest,
    LeadConvertResponse,
    LeadCreate,
    LeadRead,
    LeadUpdate,
)
from app.services import crud
from app.services.activity_service import log_activity
from app.services.lead_scoring import recompute_lead_score
from app.services.lead_service import convert_lead

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Lead:
    obj = Lead(workspace_id=ws.id, owner_user_id=user.id, **payload.model_dump(exclude_unset=True))
    obj = crud.create_scoped(session, obj)
    # Apply scoring rules on top of the caller-provided base score, then persist.
    recompute_lead_score(session, obj, base_score=obj.score)
    session.commit()
    session.refresh(obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="created",
        subject_type="lead",
        subject_id=obj.id,
        summary=f"{obj.first_name} {obj.last_name or ''}".strip(),
    )
    return obj


@router.get("", response_model=Page[LeadRead])
def list_leads(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[LeadRead]:
    base = crud.scoped_query(Lead, ws.id)
    if status_filter:
        try:
            base = base.where(Lead.status == LeadStatus(status_filter))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown lead status") from None
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Lead.created_at.desc()).limit(limit).offset(offset)).all()
    return Page[LeadRead].build([LeadRead.model_validate(r) for r in rows], total, limit, offset)


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(
    lead_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> Lead:
    return crud.get_or_404(session, Lead, ws.id, lead_id)


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Lead:
    obj = crud.get_or_404(session, Lead, ws.id, lead_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        try:
            data["status"] = LeadStatus(data["status"])
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown lead status") from None
    allowed = {"first_name", "last_name", "email", "phone", "company_name", "source", "status", "score", "notes"}
    crud.apply_updates(obj, data, allowed=allowed)
    session.add(obj)
    # Re-evaluate rules when a scored field changes. The base is the caller's
    # explicit `score` if they set one (manual override wins), otherwise 0 so
    # stale deltas from the previous rule match don't accumulate on top.
    # Bug caught in tick 19: without the reset, updating a scored field kept
    # adding new deltas onto the old score forever.
    if any(k in data for k in ("email", "company_name", "source", "status", "score")):
        base = int(data["score"]) if "score" in data and data["score"] is not None else 0
        recompute_lead_score(session, obj, base_score=base)
    session.commit()
    session.refresh(obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="updated",
        subject_type="lead",
        subject_id=obj.id,
    )
    return obj


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> None:
    obj = crud.get_or_404(session, Lead, ws.id, lead_id)
    crud.soft_delete(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="deleted",
        subject_type="lead",
        subject_id=obj.id,
    )


@router.post("/{lead_id}/convert", response_model=LeadConvertResponse)
def convert(
    lead_id: UUID,
    req: LeadConvertRequest,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> LeadConvertResponse:
    lead = crud.get_or_404(session, Lead, ws.id, lead_id)
    try:
        return convert_lead(
            session,
            workspace_id=ws.id,
            actor_user_id=user.id,
            lead=lead,
            req=req,
        )
    except ValueError as e:
        code = str(e)
        if code == "lead_already_converted":
            raise HTTPException(status.HTTP_409_CONFLICT, "Lead already converted") from None
        if code == "pipeline_has_no_stages":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Target pipeline has no stages") from None
        # Cross-workspace FK attempts return 404 (same as the missing-entity
        # case) so we don't confirm the id exists elsewhere.
        if code in ("company_not_in_workspace", "pipeline_not_in_workspace"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, code.replace("_", " ")) from None
        raise
