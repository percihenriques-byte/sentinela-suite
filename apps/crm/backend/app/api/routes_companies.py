from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Company
from app.schemas.common import Page
from app.schemas.crm import CompanyCreate, CompanyRead, CompanyUpdate
from app.services import crud
from app.services.activity_service import log_activity

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Company:
    obj = Company(workspace_id=ws.id, owner_user_id=user.id, **payload.model_dump(exclude_unset=True))
    obj = crud.create_scoped(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="created",
        subject_type="company",
        subject_id=obj.id,
        summary=obj.name,
    )
    return obj


@router.get("", response_model=Page[CompanyRead])
def list_companies(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[CompanyRead]:
    base = crud.scoped_query(Company, ws.id)
    if q:
        like = f"%{crud.like_escape(q)}%"
        base = base.where(
            Company.name.ilike(like, escape="\\") |
            Company.domain.ilike(like, escape="\\") |
            Company.industry.ilike(like, escape="\\")
        )
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Company.created_at.desc()).limit(limit).offset(offset)).all()
    return Page[CompanyRead].build([CompanyRead.model_validate(r) for r in rows], total, limit, offset)


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> Company:
    return crud.get_or_404(session, Company, ws.id, company_id)


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: UUID,
    payload: CompanyUpdate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Company:
    obj = crud.get_or_404(session, Company, ws.id, company_id)
    allowed = {"name", "domain", "industry", "size", "website", "phone", "description", "annual_revenue"}
    crud.apply_updates(obj, payload.model_dump(exclude_unset=True), allowed=allowed)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="updated",
        subject_type="company",
        subject_id=obj.id,
        summary=obj.name,
    )
    return obj


class CompanyBulkRequest(BaseModel):
    items: list[CompanyCreate] = Field(min_length=1, max_length=1000)


class CompanyBulkResponse(BaseModel):
    created: int
    failed: int
    errors: list[dict]


@router.post("/bulk", response_model=CompanyBulkResponse, status_code=status.HTTP_201_CREATED)
def bulk_create_companies(
    req: CompanyBulkRequest,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> CompanyBulkResponse:
    created = 0
    errors: list[dict] = []
    for idx, item in enumerate(req.items):
        try:
            with session.begin_nested():
                obj = Company(workspace_id=ws.id, owner_user_id=user.id, **item.model_dump(exclude_unset=True))
                session.add(obj)
                session.flush()
                log_activity(
                    session, workspace_id=ws.id, actor_user_id=user.id,
                    kind="created", subject_type="company", subject_id=obj.id,
                    summary=obj.name, commit=False,
                )
            created += 1
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})
    session.commit()
    return CompanyBulkResponse(created=created, failed=len(errors), errors=errors)


class BulkDeleteRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=1000)


class BulkDeleteResponse(BaseModel):
    deleted: int
    not_found: int


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_companies(
    req: BulkDeleteRequest,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> BulkDeleteResponse:
    deleted = 0
    not_found = 0
    for cid in req.ids:
        try:
            obj = crud.get_or_404(session, Company, ws.id, cid)
            obj.deleted_at = datetime.now(timezone.utc)
            session.add(obj)
            log_activity(
                session, workspace_id=ws.id, actor_user_id=user.id,
                kind="deleted", subject_type="company", subject_id=obj.id,
                commit=False,
            )
            deleted += 1
        except HTTPException:
            not_found += 1
    session.commit()
    return BulkDeleteResponse(deleted=deleted, not_found=not_found)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> None:
    obj = crud.get_or_404(session, Company, ws.id, company_id)
    crud.soft_delete(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="deleted",
        subject_type="company",
        subject_id=obj.id,
        summary=obj.name,
    )
