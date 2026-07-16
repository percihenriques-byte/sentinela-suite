from typing import Optional
from uuid import UUID
from sqlmodel import Field

from app.models.base import WorkspaceScopedModel


class Company(WorkspaceScopedModel, table=True):
    name: str = Field(index=True, nullable=False)
    domain: Optional[str] = Field(default=None, index=True)
    industry: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None
    annual_revenue: Optional[float] = None
    owner_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)


class Contact(WorkspaceScopedModel, table=True):
    company_id: Optional[UUID] = Field(default=None, foreign_key="company.id", index=True)
    first_name: str = Field(nullable=False)
    last_name: Optional[str] = None
    email: Optional[str] = Field(default=None, index=True)
    phone: Optional[str] = None
    mobile: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_handle: Optional[str] = None
    is_primary: bool = Field(default=False)
    notes: Optional[str] = None
    owner_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)
