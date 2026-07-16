from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from sqlmodel import Field

from app.models.base import WorkspaceScopedModel


class LeadStatus(str, Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    unqualified = "unqualified"
    converted = "converted"


class OpportunityStatus(str, Enum):
    open = "open"
    won = "won"
    lost = "lost"


class Pipeline(WorkspaceScopedModel, table=True):
    name: str = Field(nullable=False)
    description: Optional[str] = None
    is_default: bool = Field(default=False)


class PipelineStage(WorkspaceScopedModel, table=True):
    pipeline_id: UUID = Field(foreign_key="pipeline.id", index=True, nullable=False)
    name: str = Field(nullable=False)
    order_index: int = Field(default=0, nullable=False)
    probability: float = Field(default=0.0)
    is_won: bool = Field(default=False)
    is_lost: bool = Field(default=False)


class Lead(WorkspaceScopedModel, table=True):
    first_name: str = Field(nullable=False)
    last_name: Optional[str] = None
    email: Optional[str] = Field(default=None, index=True)
    phone: Optional[str] = None
    company_name: Optional[str] = None
    source: Optional[str] = None
    status: LeadStatus = Field(default=LeadStatus.new, index=True)
    score: int = Field(default=0)
    notes: Optional[str] = None
    owner_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)
    converted_contact_id: Optional[UUID] = Field(default=None, foreign_key="contact.id")
    converted_opportunity_id: Optional[UUID] = Field(default=None, foreign_key="opportunity.id")
    converted_at: Optional[datetime] = None


class Opportunity(WorkspaceScopedModel, table=True):
    name: str = Field(nullable=False)
    contact_id: Optional[UUID] = Field(default=None, foreign_key="contact.id", index=True)
    company_id: Optional[UUID] = Field(default=None, foreign_key="company.id", index=True)
    pipeline_id: UUID = Field(foreign_key="pipeline.id", index=True, nullable=False)
    stage_id: UUID = Field(foreign_key="pipelinestage.id", index=True, nullable=False)
    status: OpportunityStatus = Field(default=OpportunityStatus.open, index=True)
    amount: float = Field(default=0.0)
    currency: str = Field(default="USD")
    expected_close_date: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    probability: float = Field(default=0.0)
    description: Optional[str] = None
    owner_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)
