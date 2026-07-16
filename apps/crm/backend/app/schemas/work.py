from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Task -----------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[datetime] = None
    assignee_user_id: Optional[UUID] = None
    related_contact_id: Optional[UUID] = None
    related_company_id: Optional[UUID] = None
    related_opportunity_id: Optional[UUID] = None
    related_lead_id: Optional[UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[datetime] = None
    assignee_user_id: Optional[UUID] = None
    related_contact_id: Optional[UUID] = None
    related_company_id: Optional[UUID] = None
    related_opportunity_id: Optional[UUID] = None
    related_lead_id: Optional[UUID] = None


class TaskRead(_ORM):
    id: UUID
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assignee_user_id: Optional[UUID] = None
    related_contact_id: Optional[UUID] = None
    related_company_id: Optional[UUID] = None
    related_opportunity_id: Optional[UUID] = None
    related_lead_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


# ---- Meeting --------------------------------------------------------------

class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    location: Optional[str] = None
    video_url: Optional[str] = None
    related_contact_id: Optional[UUID] = None
    related_opportunity_id: Optional[UUID] = None
    summary: Optional[str] = None


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    video_url: Optional[str] = None
    related_contact_id: Optional[UUID] = None
    related_opportunity_id: Optional[UUID] = None
    summary: Optional[str] = None


class MeetingRead(_ORM):
    id: UUID
    title: str
    description: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    location: Optional[str] = None
    video_url: Optional[str] = None
    organizer_user_id: Optional[UUID] = None
    related_contact_id: Optional[UUID] = None
    related_opportunity_id: Optional[UUID] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---- Note -----------------------------------------------------------------

class NoteCreate(BaseModel):
    body: str = Field(min_length=1)
    related_contact_id: Optional[UUID] = None
    related_company_id: Optional[UUID] = None
    related_opportunity_id: Optional[UUID] = None
    related_lead_id: Optional[UUID] = None


class NoteUpdate(BaseModel):
    body: Optional[str] = None
    related_contact_id: Optional[UUID] = None
    related_company_id: Optional[UUID] = None
    related_opportunity_id: Optional[UUID] = None
    related_lead_id: Optional[UUID] = None


class NoteRead(_ORM):
    id: UUID
    body: str
    author_user_id: Optional[UUID] = None
    related_contact_id: Optional[UUID] = None
    related_company_id: Optional[UUID] = None
    related_opportunity_id: Optional[UUID] = None
    related_lead_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
