from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from typing import Annotated
from fastapi import Query
from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import WorkspaceRole
from app.services.demo_seed import seed_workspace
from app.services.workspace_io import export_workspace, import_workspace

router = APIRouter(prefix="/workspaces/current", tags=["workspace-io"])


@router.get("/export")
def export_current_workspace(
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> JSONResponse:
    payload = export_workspace(session, ws.id)
    return JSONResponse(
        payload,
        headers={"Content-Disposition": f"attachment; filename=visiquost-{ws.workspace.slug}.json"},
    )


@router.post("/import")
def import_into_current_workspace(
    envelope: dict,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> dict:
    ws.require_role(WorkspaceRole.owner, WorkspaceRole.admin)
    try:
        result = import_workspace(session, envelope, ws.id, user.id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None
    return result.to_dict()


@router.post("/seed-demo")
def seed_demo_data(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
    force: Annotated[bool, Query()] = False,
) -> dict:
    """Populate the workspace with a realistic sample dataset. Skips if data
    already exists unless force=true."""
    ws.require_role(WorkspaceRole.owner, WorkspaceRole.admin)
    return seed_workspace(session, ws.id, user.id, force=force)
