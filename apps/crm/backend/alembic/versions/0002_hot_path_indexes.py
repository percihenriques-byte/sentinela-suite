"""Add composite indexes on hot query paths.

Every workspace-scoped query filters by workspace_id + deleted_at IS NULL, and
most reads sort/filter by created_at or occurred_at. The Activity timeline
also groups by (subject_type, subject_id).

These indexes shave latency on Postgres for even modestly-sized workspaces.
SQLite doesn't benefit as much but the DDL is compatible.

Revision ID: 0002_hot_path_indexes
Revises: 0001_initial
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0002_hot_path_indexes"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COMPOSITE_INDEXES = [
    # Workspace-scoped soft-delete filter is on every read.
    ("ix_contact_workspace_deleted", "contact", ["workspace_id", "deleted_at"]),
    ("ix_company_workspace_deleted", "company", ["workspace_id", "deleted_at"]),
    ("ix_lead_workspace_deleted", "lead", ["workspace_id", "deleted_at"]),
    ("ix_opportunity_workspace_deleted", "opportunity", ["workspace_id", "deleted_at"]),
    ("ix_task_workspace_deleted", "task", ["workspace_id", "deleted_at"]),
    ("ix_note_workspace_deleted", "note", ["workspace_id", "deleted_at"]),
    ("ix_meeting_workspace_deleted", "meeting", ["workspace_id", "deleted_at"]),
    # Activity timeline: fetch by subject.
    ("ix_activity_subject", "activity", ["subject_type", "subject_id"]),
    ("ix_activity_workspace_occurred", "activity", ["workspace_id", "occurred_at"]),
    # Tag links: filter by subject when rendering row chips.
    ("ix_taglink_subject", "taglink", ["subject_type", "subject_id"]),
    # Jarvis message history: fetch by conversation.
    ("ix_jarvismessage_conv_created", "jarvismessage", ["conversation_id", "created_at"]),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = None
    try:
        from sqlalchemy import inspect
        inspector = inspect(bind)
    except Exception:
        inspector = None

    for name, table, cols in COMPOSITE_INDEXES:
        try:
            if inspector is not None:
                existing = {ix["name"] for ix in inspector.get_indexes(table)}
                if name in existing:
                    continue
                # Also skip if the table itself doesn't exist yet (fresh envs).
                if table not in inspector.get_table_names():
                    continue
            op.create_index(name, table, cols)
        except Exception:
            # Idempotent-ish: individual failures shouldn't abort the migration.
            pass


def downgrade() -> None:
    for name, table, _ in reversed(COMPOSITE_INDEXES):
        try:
            op.drop_index(name, table_name=table)
        except Exception:
            pass
