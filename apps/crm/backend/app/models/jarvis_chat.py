from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import Field

from app.models.base import WorkspaceScopedModel


class JarvisConversation(WorkspaceScopedModel, table=True):
    """A single chat thread between a user and Jarvis, scoped to a workspace."""
    user_id: UUID = Field(foreign_key="user.id", index=True, nullable=False)
    title: Optional[str] = None  # auto-populated from first user turn
    last_message_at: Optional[datetime] = Field(default=None, index=True)


class JarvisMessage(WorkspaceScopedModel, table=True):
    """One turn in a Jarvis conversation. Persisted so the client doesn't have
    to re-send history and so we can audit/replay what Jarvis said."""
    conversation_id: UUID = Field(foreign_key="jarvisconversation.id", index=True, nullable=False)
    role: str = Field(nullable=False)  # "user" | "assistant" | "system"
    content: str = Field(nullable=False)
    intent: Optional[str] = Field(default=None, index=True)
    tool_calls_json: Optional[str] = None  # JSON list of tool call dicts
    fallback: bool = Field(default=False)
    from_llm: bool = Field(default=False)  # True when the reply came from cloud LLM
