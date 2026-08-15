from typing import Annotated
from uuid import UUID
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlmodel import Session, select

from app.core.security import decode_token
from app.db.session import get_session
from app.models import User, Workspace, WorkspaceMember, WorkspaceRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")
    try:
        user_id = UUID(subject)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed subject") from None
    user = session.get(User, user_id)
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inactive or unknown user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[Session, Depends(get_session)]


class WorkspaceCtx:
    """Resolved workspace + membership for the current request."""

    def __init__(self, workspace: Workspace, membership: WorkspaceMember):
        self.workspace = workspace
        self.membership = membership

    @property
    def id(self) -> UUID:
        return self.workspace.id

    @property
    def role(self) -> WorkspaceRole:
        return self.membership.role

    def require_role(self, *allowed: WorkspaceRole) -> None:
        if self.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient workspace role")


def get_current_workspace(
    session: SessionDep,
    user: CurrentUser,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
) -> WorkspaceCtx:
    """Resolve workspace from X-Workspace-Id header, falling back to the user's
    first owned/joined workspace. Verifies membership on every request."""
    workspace_id: UUID | None = None
    if x_workspace_id:
        try:
            workspace_id = UUID(x_workspace_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid X-Workspace-Id") from None

    if workspace_id is None:
        membership = session.exec(
            select(WorkspaceMember)
            .where(WorkspaceMember.user_id == user.id, WorkspaceMember.deleted_at.is_(None))
            .order_by(WorkspaceMember.created_at.asc())
            .limit(1)
        ).first()
        if not membership:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "User is not a member of any workspace")
    else:
        membership = session.exec(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.deleted_at.is_(None),
            )
        ).first()
        if not membership:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this workspace")

    workspace = session.get(Workspace, membership.workspace_id)
    if not workspace or workspace.deleted_at is not None or not workspace.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Workspace is not accessible")
    return WorkspaceCtx(workspace=workspace, membership=membership)


CurrentWorkspace = Annotated[WorkspaceCtx, Depends(get_current_workspace)]


def get_responsavel_ctx(ws: CurrentWorkspace) -> WorkspaceCtx:
    """Papel "responsavel" do modulo Seguranca (ESPEC-SEGURANCA.md, secao 5).

    Nesta base, "responsavel" mapeia para owner/admin do workspace: e o adulto
    dono da instalacao, o mesmo perfil que administra o Sentinela. Membro comum
    e viewer recebem 403 — dado de seguranca (achados, incidentes, auditoria)
    nao e para qualquer membro do CRM. Fecha, para o modulo novo, o debito B6.
    """
    ws.require_role(WorkspaceRole.owner, WorkspaceRole.admin)
    return ws


CurrentResponsavel = Annotated[WorkspaceCtx, Depends(get_responsavel_ctx)]
