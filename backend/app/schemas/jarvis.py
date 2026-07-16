from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class JarvisMessageIn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class JarvisChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: Optional[UUID] = None
    history: list[JarvisMessageIn] = Field(default_factory=list, max_length=40)
    max_tool_iterations: int = Field(default=6, ge=1, le=12)


class JarvisChatResponse(BaseModel):
    reply: str
    conversation_id: Optional[UUID] = None
    intent: Optional[str] = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    fallback: bool = False
    from_llm: bool = False
    error: Optional[str] = None


class JarvisContextSnapshot(BaseModel):
    counts: dict[str, int]
    overdue_task_count: int
    upcoming_meeting_count: int
    open_opportunity_count: int
    open_opportunities: list[dict[str, Any]] = Field(default_factory=list)
    preferences: dict[str, str]
    generated_at: str
    nudges: list[dict[str, Any]] = Field(default_factory=list)


class JarvisConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class JarvisMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    intent: Optional[str] = None
    fallback: bool
    from_llm: bool
    created_at: datetime
