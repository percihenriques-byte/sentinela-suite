from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampedModel(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=_now, nullable=False)
    updated_at: datetime = Field(default_factory=_now, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, index=True)


class WorkspaceScopedModel(TimestampedModel):
    workspace_id: UUID = Field(foreign_key="workspace.id", index=True, nullable=False)
