from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Company ---------------------------------------------------------------

class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    annual_revenue: Optional[float] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    annual_revenue: Optional[float] = None


class CompanyRead(_ORM):
    id: UUID
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    annual_revenue: Optional[float] = None
    created_at: datetime
    updated_at: datetime


# ---- Contact ---------------------------------------------------------------

class ContactCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    company_id: Optional[UUID] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    company_id: Optional[UUID] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    notes: Optional[str] = None


class ContactRead(_ORM):
    id: UUID
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    company_id: Optional[UUID] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---- Lead -----------------------------------------------------------------

class LeadCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    source: Optional[str] = None
    score: int = 0
    notes: Optional[str] = None


class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    score: Optional[int] = None
    notes: Optional[str] = None


class LeadRead(_ORM):
    id: UUID
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    source: Optional[str] = None
    status: str
    score: int
    converted_at: Optional[datetime] = None
    converted_contact_id: Optional[UUID] = None
    converted_opportunity_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class LeadConvertRequest(BaseModel):
    """Convert a lead into a Contact (+ optional Company) and an Opportunity."""
    company_id: Optional[UUID] = None
    create_company: bool = False
    create_opportunity: bool = True
    opportunity_name: Optional[str] = None
    pipeline_id: Optional[UUID] = None  # falls back to the workspace default
    amount: float = 0.0
    currency: str = "USD"
    expected_close_date: Optional[datetime] = None


class LeadConvertResponse(BaseModel):
    lead_id: UUID
    contact_id: UUID
    company_id: Optional[UUID] = None
    opportunity_id: Optional[UUID] = None


# ---- Opportunity ----------------------------------------------------------

class OpportunityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    pipeline_id: Optional[UUID] = None  # falls back to the workspace default
    stage_id: Optional[UUID] = None  # falls back to the pipeline's first stage
    amount: float = 0.0
    currency: str = "USD"
    contact_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    expected_close_date: Optional[datetime] = None
    description: Optional[str] = None
    probability: float = 0.0


class OpportunityUpdate(BaseModel):
    name: Optional[str] = None
    pipeline_id: Optional[UUID] = None
    stage_id: Optional[UUID] = None
    status: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    contact_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    expected_close_date: Optional[datetime] = None
    description: Optional[str] = None
    probability: Optional[float] = None


class OpportunityRead(_ORM):
    id: UUID
    name: str
    pipeline_id: UUID
    stage_id: UUID
    status: str
    amount: float
    currency: str
    contact_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    expected_close_date: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    probability: float
    created_at: datetime
    updated_at: datetime


# ---- Pipeline / Stage -----------------------------------------------------

class PipelineStageRead(_ORM):
    id: UUID
    pipeline_id: UUID
    name: str
    order_index: int
    probability: float
    is_won: bool
    is_lost: bool


class PipelineRead(_ORM):
    id: UUID
    name: str
    description: Optional[str] = None
    is_default: bool
    stages: list[PipelineStageRead] = []
