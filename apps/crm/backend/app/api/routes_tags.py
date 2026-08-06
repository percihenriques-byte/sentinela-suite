from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Tag, TagLink
from app.schemas.common import Page
from app.services import crud
from app.services.activity_service import log_activity

router = APIRouter(prefix="/tags", tags=["tags"])

VALID_SUBJECT_TYPES = {"contact", "company", "lead", "opportunity", "task", "meeting", "note"}


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str | None = None


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    color: str | None = None


class TagAttach(BaseModel):
    subject_type: str
    subject_id: UUID


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> Tag:
    existing = session.exec(
        crud.scoped_query(Tag, ws.id).where(Tag.name == payload.name)
    ).first()
    if existing:
        return existing
    tag = Tag(workspace_id=ws.id, name=payload.name, color=payload.color)
    return crud.create_scoped(session, tag)


@router.get("", response_model=Page[TagRead])
def list_tags(session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace,
              limit: Annotated[int, Query(ge=1, le=200)] = 100,
              offset: Annotated[int, Query(ge=0)] = 0) -> Page[TagRead]:
    base = crud.scoped_query(Tag, ws.id)
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Tag.name.asc()).limit(limit).offset(offset)).all()
    return Page[TagRead].build([TagRead.model_validate(r) for r in rows], total, limit, offset)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: UUID, session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> None:
    tag = crud.get_or_404(session, Tag, ws.id, tag_id)
    crud.soft_delete(session, tag)


@router.post("/{tag_id}/attach", status_code=status.HTTP_201_CREATED)
def attach_tag(tag_id: UUID, payload: TagAttach, session: SessionDep, user: CurrentUser, ws: CurrentWorkspace) -> dict:
    tag = crud.get_or_404(session, Tag, ws.id, tag_id)
    if payload.subject_type not in VALID_SUBJECT_TYPES:
        raise HTTPException(400, f"unsupported subject_type: {payload.subject_type}")
    existing = session.exec(
        crud.scoped_query(TagLink, ws.id).where(
            TagLink.tag_id == tag.id,
            TagLink.subject_type == payload.subject_type,
            TagLink.subject_id == payload.subject_id,
        )
    ).first()
    if existing:
        return {"id": str(existing.id), "already_linked": True}
    link = TagLink(workspace_id=ws.id, tag_id=tag.id,
                   subject_type=payload.subject_type, subject_id=payload.subject_id)
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        # A concurrent request beat us to it — the DB unique index (Alembic
        # 0003) rejected the duplicate. Recover by returning the existing row.
        session.rollback()
        existing = session.exec(
            crud.scoped_query(TagLink, ws.id).where(
                TagLink.tag_id == tag.id,
                TagLink.subject_type == payload.subject_type,
                TagLink.subject_id == payload.subject_id,
            )
        ).first()
        if existing:
            return {"id": str(existing.id), "already_linked": True}
        raise
    log_activity(session, workspace_id=ws.id, actor_user_id=user.id,
                 kind="tagged", subject_type=payload.subject_type, subject_id=payload.subject_id,
                 summary=tag.name)
    return {"id": str(link.id), "tag_id": str(tag.id), "subject_id": str(payload.subject_id)}


@router.post("/{tag_id}/detach", status_code=status.HTTP_204_NO_CONTENT)
def detach_tag(tag_id: UUID, payload: TagAttach, session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> None:
    crud.get_or_404(session, Tag, ws.id, tag_id)
    link = session.exec(
        crud.scoped_query(TagLink, ws.id).where(
            TagLink.tag_id == tag_id,
            TagLink.subject_type == payload.subject_type,
            TagLink.subject_id == payload.subject_id,
        )
    ).first()
    if link:
        crud.soft_delete(session, link)


@router.get("/for/{subject_type}/{subject_id}", response_model=list[TagRead])
def tags_for_subject(subject_type: str, subject_id: UUID, session: SessionDep,
                     _user: CurrentUser, ws: CurrentWorkspace) -> list[Tag]:
    if subject_type not in VALID_SUBJECT_TYPES:
        raise HTTPException(400, f"unsupported subject_type: {subject_type}")
    links_stmt = crud.scoped_query(TagLink, ws.id).where(
        TagLink.subject_type == subject_type,
        TagLink.subject_id == subject_id,
    )
    links = session.exec(links_stmt).all()
    if not links:
        return []
    tag_ids = [l.tag_id for l in links]
    tags = session.exec(crud.scoped_query(Tag, ws.id).where(Tag.id.in_(tag_ids))).all()
    return list(tags)
