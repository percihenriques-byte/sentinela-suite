from typing import Optional
from sqlmodel import Field

from app.models.base import WorkspaceScopedModel


class LeadScoringRule(WorkspaceScopedModel, table=True):
    """A single scoring rule evaluated against every Lead.

    Rule shape (all string fields for portability):

      field: one of "email_domain", "company_name", "source", "score", "status"
      op:    one of "equals" | "iequals" | "contains" | "icontains" | "startswith"
             | "endswith" | "regex" | "gt" | "gte" | "lt" | "lte" | "in"
             | "is_present" | "is_absent"
      value: string; for numeric ops, parseable as float; for "in", CSV
      score_delta: integer to add to the lead's score when matched
      name:  human-friendly label

    Rules are additive: matched rule deltas sum into the lead score. Base score
    (whatever the caller wrote) is preserved; rules only add on top. A rule with
    score_delta=0 can act as a tag/flag without affecting the number.
    """
    name: str = Field(nullable=False)
    field: str = Field(nullable=False)
    op: str = Field(nullable=False)
    value: Optional[str] = Field(default=None)
    score_delta: int = Field(default=0)
    is_active: bool = Field(default=True)
    order_index: int = Field(default=0)
