import re
from datetime import datetime, timezone
from sqlmodel import Session, select

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models import User, Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.auth import RegisterRequest, LoginRequest, TokenPair


_slug_re = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    slug = _slug_re.sub("-", name.lower()).strip("-")
    return slug or "workspace"


def _unique_slug(session: Session, base: str) -> str:
    slug = base
    i = 1
    while session.exec(select(Workspace).where(Workspace.slug == slug)).first():
        i += 1
        slug = f"{base}-{i}"
    return slug


def register(session: Session, req: RegisterRequest) -> tuple[User, Workspace, TokenPair]:
    existing = session.exec(select(User).where(User.email == req.email)).first()
    if existing:
        raise ValueError("email_taken")

    user = User(
        email=str(req.email),
        full_name=req.full_name,
        password_hash=hash_password(req.password),
    )
    session.add(user)
    session.flush()  # obtain user.id before workspace creation

    workspace = Workspace(
        name=req.workspace_name,
        slug=_unique_slug(session, _slugify(req.workspace_name)),
        owner_id=user.id,
    )
    session.add(workspace)
    session.flush()

    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.owner))
    session.commit()
    session.refresh(user)
    session.refresh(workspace)

    tokens = TokenPair(
        access_token=create_access_token(str(user.id), extra={"ws": str(workspace.id)}),
        refresh_token=create_refresh_token(str(user.id)),
    )
    return user, workspace, tokens


def login(session: Session, req: LoginRequest) -> tuple[User, TokenPair]:
    user = session.exec(select(User).where(User.email == req.email)).first()
    if not user or not user.is_active or user.deleted_at is not None:
        raise ValueError("invalid_credentials")
    if not verify_password(req.password, user.password_hash):
        raise ValueError("invalid_credentials")
    tokens = TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
    return user, tokens
