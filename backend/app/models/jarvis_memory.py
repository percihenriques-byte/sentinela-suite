from typing import Optional
from uuid import UUID
from sqlmodel import Field

from app.models.base import WorkspaceScopedModel


class JarvisMemory(WorkspaceScopedModel, table=True):
    """Per-user/workspace preference + fact store consulted by Jarvis on every turn.

    Semantic: append-mostly. Newer records override older ones with the same key
    (resolved in the context builder), but old records are retained for audit.
    """
    user_id: UUID = Field(foreign_key="user.id", index=True, nullable=False)
    key: str = Field(index=True, nullable=False)
    value: str = Field(nullable=False)  # JSON-serialized; free-form for now
    kind: str = Field(default="preference", index=True)  # preference | fact | style | routine
    confidence: float = Field(default=1.0)
    source: Optional[str] = None  # e.g. "user_told_me", "inferred_from_activity"
