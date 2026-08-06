"""Prevent duplicate TagLinks across concurrent attach requests.

Two concurrent POSTs to `/tags/{id}/attach` for the same subject can both
observe "no existing link" and both insert. A UNIQUE index on
(workspace_id, tag_id, subject_type, subject_id) makes the second insert fail
cleanly at the DB level so the app just returns "already linked".

Revision ID: 0003_taglink_unique
Revises: 0002_hot_path_indexes
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003_taglink_unique"
down_revision: Union[str, None] = "0002_hot_path_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "uq_taglink_ws_tag_subject"


def upgrade() -> None:
    bind = op.get_bind()
    try:
        from sqlalchemy import inspect
        inspector = inspect(bind)
        if "taglink" not in inspector.get_table_names():
            return
        existing = {ix["name"] for ix in inspector.get_indexes("taglink")}
        if INDEX_NAME in existing:
            return
    except Exception:
        pass
    op.create_index(
        INDEX_NAME,
        "taglink",
        ["workspace_id", "tag_id", "subject_type", "subject_id"],
        unique=True,
    )


def downgrade() -> None:
    try:
        op.drop_index(INDEX_NAME, table_name="taglink")
    except Exception:
        pass
