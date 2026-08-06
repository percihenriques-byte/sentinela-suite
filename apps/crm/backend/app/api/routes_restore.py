"""Generic restore endpoint — undoes a soft-delete within a short window.

Powers the frontend's "Undo" toast for any deletion. Guarded to only allow
restoring items deleted in the last 10 minutes so this can't be used to
resurrect ancient data.
"""
from datetime import datetime, timedelta, timezone
from typing import Type
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Contact, Company, Lead, Opportunity, Task, Meeting, Note


router = APIRouter(prefix="/restore", tags=["restore"])

MODEL_MAP: dict[str, Type] = {
    "contact": Contact, "company": Company, "lead": Lead,
    "opportunity": Opportunity, "task": Task, "meeting": Meeting, "note": Note,
}

RESTORE_WINDOW = timedelta(minutes=10)


@router.post("/{kind}/{item_id}")
def restore_item(
    kind: str,
    item_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> dict:
    model = MODEL_MAP.get(kind)
    if not model:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown kind '{kind}'")
    obj = session.exec(
        select(model).where(model.workspace_id == ws.id, model.id == item_id)
    ).first()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    if obj.deleted_at is None:
        return {"status": "ok", "kind": kind, "id": str(item_id), "message": "not deleted"}
    deleted = obj.deleted_at if obj.deleted_at.tzinfo else obj.deleted_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - deleted > RESTORE_WINDOW:
        raise HTTPException(status.HTTP_410_GONE, "restore window expired (10 min)")
    obj.deleted_at = None
    session.add(obj)
    session.commit()
    return {"status": "restored", "kind": kind, "id": str(item_id)}
