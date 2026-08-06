from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import Field

from app.models.base import WorkspaceScopedModel


class ExternalAccount(WorkspaceScopedModel, table=True):
    """A connected third-party account (Google, Microsoft, Slack, etc.)."""
    user_id: UUID = Field(foreign_key="user.id", index=True, nullable=False)
    provider: str = Field(nullable=False, index=True)  # google | microsoft | slack | ...
    account_label: Optional[str] = None  # e.g. the user's email at the provider
    scopes: Optional[str] = None  # space-separated
    access_token_enc: str = Field(nullable=False)  # Fernet-encrypted
    refresh_token_enc: Optional[str] = None
    token_type: str = Field(default="bearer")
    expires_at: Optional[datetime] = None
    is_active: bool = Field(default=True)
