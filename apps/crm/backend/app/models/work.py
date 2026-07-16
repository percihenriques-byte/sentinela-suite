from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from sqlmodel import Field

from app.models.base import WorkspaceScopedModel


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    cancelled = "cancelled"


class TaskPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class Task(WorkspaceScopedModel, table=True):
    title: str = Field(nullable=False)
    description: Optional[str] = None
    status: TaskStatus = Field(default=TaskStatus.todo, index=True)
    priority: TaskPriority = Field(default=TaskPriority.normal, index=True)
    due_at: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = None
    assignee_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)
    related_contact_id: Optional[UUID] = Field(default=None, foreign_key="contact.id")
    related_company_id: Optional[UUID] = Field(default=None, foreign_key="company.id")
    related_opportunity_id: Optional[UUID] = Field(default=None, foreign_key="opportunity.id")
    related_lead_id: Optional[UUID] = Field(default=None, foreign_key="lead.id")


class Meeting(WorkspaceScopedModel, table=True):
    title: str = Field(nullable=False)
    description: Optional[str] = None
    starts_at: datetime = Field(nullable=False, index=True)
    ends_at: datetime = Field(nullable=False)
    location: Optional[str] = None
    video_url: Optional[str] = None
    organizer_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)
    related_contact_id: Optional[UUID] = Field(default=None, foreign_key="contact.id")
    related_opportunity_id: Optional[UUID] = Field(default=None, foreign_key="opportunity.id")
    summary: Optional[str] = None


class Note(WorkspaceScopedModel, table=True):
    author_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)
    body: str = Field(nullable=False)
    related_contact_id: Optional[UUID] = Field(default=None, foreign_key="contact.id", index=True)
    related_company_id: Optional[UUID] = Field(default=None, foreign_key="company.id", index=True)
    related_opportunity_id: Optional[UUID] = Field(default=None, foreign_key="opportunity.id", index=True)
    related_lead_id: Optional[UUID] = Field(default=None, foreign_key="lead.id", index=True)


class Activity(WorkspaceScopedModel, table=True):
    """Append-only audit-style timeline entry for interactions."""
    actor_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)
    kind: str = Field(index=True, nullable=False)  # created, updated, email, call, note, meeting, stage_changed, ...
    subject_type: str = Field(index=True, nullable=False)  # contact, company, lead, opportunity, task, meeting
    subject_id: UUID = Field(index=True, nullable=False)
    summary: Optional[str] = None
    data: Optional[str] = None  # JSON payload with details (kept as text for SQLite portability)
    occurred_at: datetime = Field(index=True, nullable=False)
