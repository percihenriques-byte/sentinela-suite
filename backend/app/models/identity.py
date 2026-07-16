from enum import Enum
from typing import Optional
from uuid import UUID
from sqlmodel import Field

from app.models.base import TimestampedModel


class WorkspaceRole(str, Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    viewer = "viewer"


class User(TimestampedModel, table=True):
    email: str = Field(index=True, unique=True, nullable=False)
    full_name: Optional[str] = None
    password_hash: str = Field(nullable=False)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    locale: str = Field(default="en")
    timezone: str = Field(default="UTC")


class Workspace(TimestampedModel, table=True):
    name: str = Field(index=True, nullable=False)
    slug: str = Field(index=True, unique=True, nullable=False)
    owner_id: UUID = Field(foreign_key="user.id", nullable=False, index=True)
    is_active: bool = Field(default=True)
    plan: str = Field(default="free")


class WorkspaceMember(TimestampedModel, table=True):
    workspace_id: UUID = Field(foreign_key="workspace.id", nullable=False, index=True)
    user_id: UUID = Field(foreign_key="user.id", nullable=False, index=True)
    role: WorkspaceRole = Field(default=WorkspaceRole.member, nullable=False)
