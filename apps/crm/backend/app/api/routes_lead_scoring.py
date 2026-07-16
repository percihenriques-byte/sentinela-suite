from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import LeadScoringRule
from app.schemas.common import Page
from app.services import crud
from app.services.lead_scoring import recompute_all

router = APIRouter(prefix="/lead-scoring", tags=["lead-scoring"])


ALLOWED_FIELDS = {"email_domain", "company_name", "source", "score", "status", "first_name", "last_name", "notes"}
ALLOWED_OPS = {
    "equals", "iequals", "contains", "icontains", "startswith", "endswith",
    "regex", "gt", "gte", "lt", "lte", "in", "is_present", "is_absent",
}


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    field: str
    op: str
    value: str | None = None
    score_delta: int = 0
    is_active: bool = True
    order_index: int = 0


class RuleUpdate(BaseModel):
    name: str | None = None
    field: str | None = None
    op: str | None = None
    value: str | None = None
    score_delta: int | None = None
    is_active: bool | None = None
    order_index: int | None = None


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    field: str
    op: str
    value: str | None = None
    score_delta: int
    is_active: bool
    order_index: int


def _validate(field: str | None, op: str | None) -> None:
    from fastapi import HTTPException
    if field is not None and field not in ALLOWED_FIELDS:
        raise HTTPException(400, f"unsupported field: {field}. Allowed: {sorted(ALLOWED_FIELDS)}")
    if op is not None and op not in ALLOWED_OPS:
        raise HTTPException(400, f"unsupported op: {op}. Allowed: {sorted(ALLOWED_OPS)}")


@router.post("/rules", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreate,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> LeadScoringRule:
    _validate(payload.field, payload.op)
    rule = LeadScoringRule(workspace_id=ws.id, **payload.model_dump())
    return crud.create_scoped(session, rule)


@router.get("/rules", response_model=Page[RuleRead])
def list_rules(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RuleRead]:
    base = crud.scoped_query(LeadScoringRule, ws.id)
    total = crud.count_from(session, base)
    rows = session.exec(
        base.order_by(LeadScoringRule.order_index.asc(), LeadScoringRule.created_at.asc())
        .limit(limit).offset(offset)
    ).all()
    return Page[RuleRead].build([RuleRead.model_validate(r) for r in rows], total, limit, offset)


@router.patch("/rules/{rule_id}", response_model=RuleRead)
def update_rule(
    rule_id: UUID,
    payload: RuleUpdate,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> LeadScoringRule:
    rule = crud.get_or_404(session, LeadScoringRule, ws.id, rule_id)
    data = payload.model_dump(exclude_unset=True)
    _validate(data.get("field"), data.get("op"))
    allowed = {"name", "field", "op", "value", "score_delta", "is_active", "order_index"}
    crud.apply_updates(rule, data, allowed=allowed)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> None:
    rule = crud.get_or_404(session, LeadScoringRule, ws.id, rule_id)
    crud.soft_delete(session, rule)


@router.post("/recalculate")
def recalculate(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    reset_to_zero: Annotated[bool, Query()] = True,
) -> dict:
    return recompute_all(session, ws.id, reset_to_zero=reset_to_zero)
