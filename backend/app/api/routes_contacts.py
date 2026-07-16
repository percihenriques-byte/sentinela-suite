from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Company, Contact
from app.schemas.common import Page
from app.schemas.crm import ContactCreate, ContactRead, ContactUpdate
from app.services import crud
from app.services.activity_service import log_activity

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _validate_company(session, workspace_id, company_id):
    if company_id is None:
        return
    company = crud.get_or_404(session, Company, workspace_id, company_id)
    if company.deleted_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Company is deleted")


@router.get("/vcards.vcf")
def export_all_vcards(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    limit: Annotated[int, Query(ge=1, le=5000)] = 2000,
):
    """Export all contacts as a single concatenated vCard file — one file, many cards."""
    from fastapi.responses import PlainTextResponse
    contacts = list(session.exec(
        crud.scoped_query(Contact, ws.id).order_by(Contact.first_name.asc()).limit(limit)
    ).all())
    blocks = []
    for c in contacts:
        fn = f"{c.first_name or ''} {c.last_name or ''}".strip() or "Contact"
        lines = [
            "BEGIN:VCARD", "VERSION:3.0",
            f"FN:{fn}",
            f"N:{c.last_name or ''};{c.first_name or ''};;;",
        ]
        if c.email:
            lines.append(f"EMAIL;TYPE=INTERNET:{c.email}")
        if c.phone:
            lines.append(f"TEL;TYPE=WORK,VOICE:{c.phone}")
        if c.mobile:
            lines.append(f"TEL;TYPE=CELL,VOICE:{c.mobile}")
        if c.job_title:
            lines.append(f"TITLE:{c.job_title}")
        if c.department:
            lines.append(f"ORG:{c.department}")
        lines.append("END:VCARD")
        blocks.append("\r\n".join(lines))
    body = ("\r\n".join(blocks) + "\r\n") if blocks else ""
    return PlainTextResponse(
        body, media_type="text/vcard; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"visiquost-contacts-{ws.workspace.slug}.vcf\""},
    )


@router.get("/{contact_id}/vcard")
def export_contact_vcard(
    contact_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
):
    """Export a single contact as vCard 3.0 — universal, works with any address book."""
    from fastapi.responses import PlainTextResponse
    c = crud.get_or_404(session, Contact, ws.id, contact_id)
    fn = f"{c.first_name or ''} {c.last_name or ''}".strip() or "Contact"
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{fn}",
        f"N:{c.last_name or ''};{c.first_name or ''};;;",
    ]
    if c.email:
        lines.append(f"EMAIL;TYPE=INTERNET:{c.email}")
    if c.phone:
        lines.append(f"TEL;TYPE=WORK,VOICE:{c.phone}")
    if c.mobile:
        lines.append(f"TEL;TYPE=CELL,VOICE:{c.mobile}")
    if c.job_title:
        lines.append(f"TITLE:{c.job_title}")
    if c.department:
        lines.append(f"ORG:{c.department}")
    if c.notes:
        # Escape newlines for vCard
        notes = c.notes.replace("\n", "\\n").replace(",", "\\,")
        lines.append(f"NOTE:{notes}")
    lines.append("END:VCARD")
    body = "\r\n".join(lines) + "\r\n"
    return PlainTextResponse(
        body, media_type="text/vcard; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{fn.replace(' ', '_')}.vcf\""},
    )


@router.get("/find-duplicates")
def find_duplicate_contacts(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    email: Annotated[str | None, Query(max_length=200)] = None,
    first_name: Annotated[str | None, Query(max_length=100)] = None,
    last_name: Annotated[str | None, Query(max_length=100)] = None,
) -> dict:
    """Suggest possible duplicates before creating a contact.

    Order of confidence: exact email > exact first+last > fuzzy first+last.
    Returns [] if nothing suspicious.
    """
    from sqlmodel import select, or_, and_
    if not any((email, first_name, last_name)):
        return {"matches": []}
    query = crud.scoped_query(Contact, ws.id)
    conds = []
    if email:
        conds.append(Contact.email.ilike(email, escape="\\"))
    if first_name and last_name:
        conds.append(and_(
            Contact.first_name.ilike(f"%{crud.like_escape(first_name)}%", escape="\\"),
            Contact.last_name.ilike(f"%{crud.like_escape(last_name)}%", escape="\\"),
        ))
    elif first_name:
        conds.append(Contact.first_name.ilike(f"%{crud.like_escape(first_name)}%", escape="\\"))
    if not conds:
        return {"matches": []}
    rows = list(session.exec(query.where(or_(*conds)).limit(5)).all())
    return {
        "matches": [
            {
                "id": str(c.id),
                "first_name": c.first_name,
                "last_name": c.last_name,
                "email": c.email,
                "reason": "email" if email and c.email and c.email.lower() == email.lower() else "name",
            }
            for c in rows
        ]
    }


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Contact:
    data = payload.model_dump(exclude_unset=True)
    _validate_company(session, ws.id, data.get("company_id"))
    obj = Contact(workspace_id=ws.id, owner_user_id=user.id, **data)
    obj = crud.create_scoped(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="created",
        subject_type="contact",
        subject_id=obj.id,
        summary=f"{obj.first_name} {obj.last_name or ''}".strip(),
    )
    return obj


@router.get("", response_model=Page[ContactRead])
def list_contacts(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=200)] = None,
    company_id: Annotated[UUID | None, Query()] = None,
) -> Page[ContactRead]:
    base = crud.scoped_query(Contact, ws.id)
    if q:
        like = f"%{crud.like_escape(q)}%"
        base = base.where(
            Contact.first_name.ilike(like, escape="\\") |
            Contact.last_name.ilike(like, escape="\\") |
            Contact.email.ilike(like, escape="\\") |
            Contact.phone.ilike(like, escape="\\")
        )
    if company_id is not None:
        base = base.where(Contact.company_id == company_id)
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(Contact.created_at.desc()).limit(limit).offset(offset)).all()
    return Page[ContactRead].build([ContactRead.model_validate(r) for r in rows], total, limit, offset)


@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(
    contact_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> Contact:
    return crud.get_or_404(session, Contact, ws.id, contact_id)


@router.patch("/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: UUID,
    payload: ContactUpdate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> Contact:
    obj = crud.get_or_404(session, Contact, ws.id, contact_id)
    data = payload.model_dump(exclude_unset=True)
    if "company_id" in data:
        _validate_company(session, ws.id, data["company_id"])
    allowed = {"first_name", "last_name", "email", "phone", "mobile", "company_id", "job_title", "department", "notes"}
    crud.apply_updates(obj, data, allowed=allowed)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="updated",
        subject_type="contact",
        subject_id=obj.id,
    )
    return obj


class ContactBulkRequest(BaseModel):
    items: list[ContactCreate] = Field(min_length=1, max_length=1000)


class ContactBulkResponse(BaseModel):
    created: int
    failed: int
    errors: list[dict]


@router.post("/bulk", response_model=ContactBulkResponse, status_code=status.HTTP_201_CREATED)
def bulk_create_contacts(
    req: ContactBulkRequest,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> ContactBulkResponse:
    created = 0
    errors: list[dict] = []
    for idx, item in enumerate(req.items):
        # Nested SAVEPOINT so one bad row (FK failure, validation) rolls back
        # only its own scope. Without this, a flush() failure leaves the outer
        # transaction poisoned and all subsequent rows fail.
        try:
            with session.begin_nested():
                data = item.model_dump(exclude_unset=True)
                _validate_company(session, ws.id, data.get("company_id"))
                obj = Contact(workspace_id=ws.id, owner_user_id=user.id, **data)
                session.add(obj)
                session.flush()
                log_activity(
                    session, workspace_id=ws.id, actor_user_id=user.id,
                    kind="created", subject_type="contact", subject_id=obj.id,
                    summary=f"{obj.first_name} {obj.last_name or ''}".strip(),
                    commit=False,
                )
            created += 1
        except HTTPException as e:
            errors.append({"index": idx, "error": e.detail})
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})
    session.commit()
    return ContactBulkResponse(created=created, failed=len(errors), errors=errors)


class BulkDeleteRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=1000)


class BulkDeleteResponse(BaseModel):
    deleted: int
    not_found: int


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_contacts(
    req: BulkDeleteRequest,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> BulkDeleteResponse:
    deleted = 0
    not_found = 0
    for cid in req.ids:
        try:
            obj = crud.get_or_404(session, Contact, ws.id, cid)
            obj.deleted_at = datetime.now(timezone.utc)
            session.add(obj)
            log_activity(
                session, workspace_id=ws.id, actor_user_id=user.id,
                kind="deleted", subject_type="contact", subject_id=obj.id,
                commit=False,
            )
            deleted += 1
        except HTTPException:
            not_found += 1
    session.commit()
    return BulkDeleteResponse(deleted=deleted, not_found=not_found)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> None:
    obj = crud.get_or_404(session, Contact, ws.id, contact_id)
    crud.soft_delete(session, obj)
    log_activity(
        session,
        workspace_id=ws.id,
        actor_user_id=user.id,
        kind="deleted",
        subject_type="contact",
        subject_id=obj.id,
    )
