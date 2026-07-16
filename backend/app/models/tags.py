from typing import Optional
from uuid import UUID
from sqlmodel import Field

from app.models.base import WorkspaceScopedModel


class Tag(WorkspaceScopedModel, table=True):
    name: str = Field(index=True, nullable=False)
    color: Optional[str] = Field(default=None)


class TagLink(WorkspaceScopedModel, table=True):
    """Polymorphic link between a tag and any workspace entity."""
    tag_id: UUID = Field(foreign_key="tag.id", index=True, nullable=False)
    subject_type: str = Field(index=True, nullable=False)
    subject_id: UUID = Field(index=True, nullable=False)
