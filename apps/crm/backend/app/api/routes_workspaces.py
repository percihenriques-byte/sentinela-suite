"""List the workspaces the current user has access to.

The frontend calls GET /api/v1/workspaces to bootstrap the current workspace
context (it takes the first entry). Previously only workspace-scoped routes
existed (`/workspaces/current/*`), so this call 404'd on every page load.
"""
from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.models import Workspace, WorkspaceMember

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("")
def list_my_workspaces(session: SessionDep, user: CurrentUser) -> list[dict]:
    """Return workspaces the current user is a member of, newest first."""
    from sqlmodel import select
    stmt = (
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            WorkspaceMember.user_id == user.id,
            Workspace.deleted_at.is_(None),
        )
        .order_by(Workspace.created_at.desc())
    )
    rows = session.exec(stmt).all()
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "slug": w.slug,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in rows
    ]
