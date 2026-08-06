from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Company, Contact, Opportunity, OpportunityStatus
from app.schemas.common import Page
from app.schemas.crm import OpportunityCreate, OpportunityRead, OpportunityUpdate
from app.services import crud, pipeline_service
from app.services.activity_service import log_activity

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _resolve_pipeline_and_stage(session, workspace_id, pipeline_id, stage_id):
    if pipeline_id is None:
        pipeline_id = pipeline_service.get_default_pipeline(session, workspace_id).id
    try:
        stage = pipeline_service.resolve_stage(session, workspace_id, pipeline_id, stage_id)
    except ValueError as e:
        code = str(e)
        if code == "stage_not_in_pipeline":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stage does not belong to the pipeline") from None
        if code == "pipeline_has_no_stages":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pipeline has no stages") from None
        raise
    return pipeline_id, stage


@router.post("", response_model=OpportunityRead, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Opportunity:
    pipeline_id, stage = _resolve_pipeline_and_stage(session, ws.id, payload.pipeline_id, payload.stage_id)
    crud.verify_scoped_exists(session, Contact, ws.id, payload.contact_id, label="contact")
    crud.verify_scoped_exists(session, Company, ws.id, payload.company_id, label="company")
    obj = Opportunity(
        workspace_id=ws.id,
        owner_user_id=user.id,
        name=payload.name,
        pipeline_id=pipeline_id,
        stage_id=stage.id,
        amount=payload.amount,
        currency=payload.currency,
        contact_id=payload.contact_id,
        company_id=payload.company_id,
        expected_close_date=payload.expected_close_date,
        description=payload.description,
        probability=payload.probability or stage.probability,
    )
    obj = crud.create_scoped(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="created",
        subject_type="opportunity",
        subject_id=obj.id,
        summary=obj.name,
    )
    return obj


@router.get("", response_model=Page[OpportunityRead])
def list_opportunities(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    pipeline_id: Annotated[UUID | None, Query()] = None,
    stage_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[OpportunityRead]:
    base = crud.scoped_query(Opportunity, ws.id)
    if status_filter:
        try:
            base = base.where(Opportunity.status == OpportunityStatus(status_filter))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown opportunity status") from None
    if pipeline_id is not None:
        base = base.where(Opportunity.pipeline_id == pipeline_id)
    if stage_id is not None:
        base = base.where(Opportunity.stage_id == stage_id)
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Opportunity.amount.desc()).limit(limit).offset(offset)).all()
    return Page[OpportunityRead].build([OpportunityRead.model_validate(r) for r in rows], total, limit, offset)


@router.get("/{opportunity_id}", response_model=OpportunityRead)
def get_opportunity(
    opportunity_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> Opportunity:
    return crud.get_or_404(session, Opportunity, ws.id, opportunity_id)


@router.patch("/{opportunity_id}", response_model=OpportunityRead)
def update_opportunity(
    opportunity_id: UUID,
    payload: OpportunityUpdate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Opportunity:
    obj = crud.get_or_404(session, Opportunity, ws.id, opportunity_id)
    data = payload.model_dump(exclude_unset=True)
    # Tenant guards: reject caller-supplied FKs that don't belong here.
    if "contact_id" in data:
        crud.verify_scoped_exists(session, Contact, ws.id, data["contact_id"], label="contact")
    if "company_id" in data:
        crud.verify_scoped_exists(session, Company, ws.id, data["company_id"], label="company")
    new_pipeline_id = data.get("pipeline_id", obj.pipeline_id)
    new_stage_id = data.get("stage_id")
    stage_changed = False
    if "pipeline_id" in data or "stage_id" in data:
        # If the pipeline is changing but the caller didn't pick a new stage,
        # don't reuse the old stage_id — it belongs to the previous pipeline
        # and the resolver would raise "stage_not_in_pipeline". Instead let the
        # resolver pick the first stage of the new pipeline by passing None.
        # (Bug caught in tick 23 — PATCHing pipeline_id alone was a 400.)
        pipeline_changed = "pipeline_id" in data and data["pipeline_id"] != obj.pipeline_id
        fallback_stage = None if pipeline_changed else obj.stage_id
        stage_hint = new_stage_id or fallback_stage
        pipeline_id, stage = _resolve_pipeline_and_stage(session, ws.id, new_pipeline_id, stage_hint)
        stage_changed = stage.id != obj.stage_id
        data["pipeline_id"] = pipeline_id
        data["stage_id"] = stage.id
        # Snap probability to the destination stage on every move. Bug caught
        # in tick 28: PATCHing an opp into "Won" left probability at whatever
        # the previous stage was (e.g. 10% from Prospecting) instead of 100%.
        # Callers can still override by passing an explicit `probability` in
        # the body — `setdefault` respects it.
        if stage.is_won:
            data.setdefault("status", OpportunityStatus.won.value)
            data.setdefault("probability", 100.0)
            obj.closed_at = datetime.now(timezone.utc)
        elif stage.is_lost:
            data.setdefault("status", OpportunityStatus.lost.value)
            data.setdefault("probability", 0.0)
            obj.closed_at = datetime.now(timezone.utc)
        else:
            data.setdefault("probability", stage.probability)
    if "status" in data and isinstance(data["status"], str):
        try:
            data["status"] = OpportunityStatus(data["status"])
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown opportunity status") from None
    allowed = {
        "name", "pipeline_id", "stage_id", "status", "amount", "currency",
        "contact_id", "company_id", "expected_close_date", "description", "probability",
    }
    crud.apply_updates(obj, data, allowed=allowed)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="stage_changed" if stage_changed else "updated",
        subject_type="opportunity",
        subject_id=obj.id,
        summary=obj.name,
    )
    return obj


@router.delete("/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opportunity(
    opportunity_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> None:
    obj = crud.get_or_404(session, Opportunity, ws.id, opportunity_id)
    crud.soft_delete(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="deleted",
        subject_type="opportunity",
        subject_id=obj.id,
    )
