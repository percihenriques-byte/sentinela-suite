from typing import Annotated
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Activity
from app.schemas.common import Page
from app.services import crud

router = APIRouter(prefix="/activities", tags=["activities"])


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    subject_type: str
    subject_id: UUID
    summary: str | None = None
    actor_user_id: UUID | None = None
    occurred_at: datetime
    created_at: datetime


@router.get("", response_model=Page[ActivityRead])
def list_activities(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    subject_type: Annotated[str | None, Query()] = None,
    subject_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ActivityRead]:
    base = crud.scoped_query(Activity, ws.id)
    if subject_type:
        base = base.where(Activity.subject_type == subject_type)
    if subject_id is not None:
        base = base.where(Activity.subject_id == subject_id)
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Activity.occurred_at.desc()).limit(limit).offset(offset)).all()
    return Page[ActivityRead].build([ActivityRead.model_validate(r) for r in rows], total, limit, offset)
