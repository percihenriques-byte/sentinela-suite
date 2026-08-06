"""Workspace-scoped export + import.

Serializes every workspace-scoped row into a portable JSON envelope so the user
can back up their data, move between installations, or archive an org. Keeps
the same UUIDs on import when the destination workspace is empty; regenerates
them otherwise to avoid collisions.

The export deliberately excludes cross-workspace identity (User, Workspace,
WorkspaceMember). Import runs inside the *current* workspace of the caller.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID, uuid4

from sqlmodel import Session, select

from app.models import (
    Activity,
    Company,
    Contact,
    JarvisConversation,
    JarvisMemory,
    JarvisMessage,
    Lead,
    Meeting,
    Note,
    Opportunity,
    Pipeline,
    PipelineStage,
    Tag,
    TagLink,
    Task,
)


EXPORTABLE = [
    # Order matters for FK-enforcing databases (Postgres). Insert parents first.
    ("companies", Company),
    ("contacts", Contact),
    ("pipelines", Pipeline),
    ("pipeline_stages", PipelineStage),
    ("opportunities", Opportunity),   # before Lead — leads may reference converted_opportunity_id
    ("leads", Lead),
    ("tasks", Task),
    ("meetings", Meeting),
    ("notes", Note),
    ("activities", Activity),
    ("tags", Tag),
    ("tag_links", TagLink),
    ("jarvis_conversations", JarvisConversation),
    ("jarvis_messages", JarvisMessage),
    ("jarvis_memory", JarvisMemory),
]

EXPORT_VERSION = 1


def _row_to_dict(obj: Any) -> dict[str, Any]:
    """SQLModel .model_dump but stringify UUIDs and datetimes for JSON."""
    d = obj.model_dump()
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, UUID):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def export_workspace(session: Session, workspace_id: UUID) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "version": EXPORT_VERSION,
        # Use timezone-aware `now(utc)` — Python 3.12 deprecated the naive `utcnow()`.
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "workspace_id": str(workspace_id),
        "entities": {},
    }
    for name, model in EXPORTABLE:
        stmt = select(model).where(model.workspace_id == workspace_id)
        envelope["entities"][name] = [_row_to_dict(r) for r in session.exec(stmt).all()]
    return envelope


@dataclass
class ImportResult:
    counts: dict[str, int]
    workspace_id: UUID
    remapped: bool  # True if UUIDs were regenerated to avoid collisions

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": self.counts,
            "workspace_id": str(self.workspace_id),
            "remapped": self.remapped,
        }


def _workspace_has_data(session: Session, workspace_id: UUID) -> bool:
    for _, model in EXPORTABLE:
        row = session.exec(select(model).where(model.workspace_id == workspace_id).limit(1)).first()
        if row is not None:
            return True
    return False


_UUID_FIELDS_HINT: set[str] = {
    "id", "workspace_id", "user_id", "owner_user_id", "actor_user_id",
    "author_user_id", "assignee_user_id", "organizer_user_id",
    "company_id", "contact_id", "lead_id", "opportunity_id", "pipeline_id",
    "stage_id", "conversation_id", "subject_id", "tag_id",
    "converted_contact_id", "converted_opportunity_id",
    "related_contact_id", "related_company_id", "related_opportunity_id", "related_lead_id",
}


def import_workspace(
    session: Session,
    envelope: dict[str, Any],
    target_workspace_id: UUID,
    actor_user_id: UUID,
) -> ImportResult:
    if not isinstance(envelope, dict) or "entities" not in envelope:
        raise ValueError("invalid_envelope")
    if envelope.get("version") != EXPORT_VERSION:
        raise ValueError("unsupported_version")

    entities = envelope["entities"]
    remap: dict[str, str] = {}  # old_id → new_id

    # Always remap. Ids are globally unique across the DB — if the source
    # workspace's data is still around (or was ever imported before), keeping
    # the original ids risks a UNIQUE-constraint violation on the entity's
    # primary key. Regenerating every id is boring but safe.
    remap_needed = True
    for name, _ in EXPORTABLE:
        for row in entities.get(name, []):
            old_id = row.get("id")
            if old_id:
                remap[str(old_id)] = str(uuid4())

    def _fix(row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        # Never trust workspace_id from the file — always target the caller's ws.
        row["workspace_id"] = str(target_workspace_id)
        # User-owned refs: retarget to the importing user so authz is coherent.
        for k in ("user_id", "owner_user_id", "actor_user_id", "author_user_id",
                  "assignee_user_id", "organizer_user_id"):
            if k in row and row[k] is not None:
                row[k] = str(actor_user_id)
        if remap_needed:
            for k, v in list(row.items()):
                if k in _UUID_FIELDS_HINT and v is not None and str(v) in remap:
                    row[k] = remap[str(v)]
        return row

    def _coerce_types(row: dict[str, Any]) -> dict[str, Any]:
        # SQLAlchemy 2's typed columns are strict: UUID cols call `.hex`,
        # DateTime cols reject strings. The export envelope is JSON, so every
        # UUID + datetime is a string on the way in. Coerce them back.
        for k, v in list(row.items()):
            if v is None or not isinstance(v, str):
                continue
            if k == "id" or k in _UUID_FIELDS_HINT:
                try:
                    row[k] = UUID(v)
                    continue
                except ValueError:
                    pass
            # Timestamp-ish column names. Cheap heuristic — good enough for our
            # models (`created_at`, `updated_at`, `deleted_at`, `occurred_at`,
            # `starts_at`, `ends_at`, `due_at`, `completed_at`, `converted_at`,
            # `closed_at`, `expected_close_date`, `last_message_at`,
            # `expires_at`, `started_at`, `finished_at`, `last_run_at`).
            if k.endswith("_at") or k.endswith("_date"):
                try:
                    row[k] = datetime.fromisoformat(v.replace("Z", "+00:00"))
                except ValueError:
                    pass
        return row

    counts: dict[str, int] = {}
    for name, model in EXPORTABLE:
        rows = entities.get(name, [])
        counts[name] = 0
        for raw in rows:
            fixed = _coerce_types(_fix(raw))
            # Drop keys not present on the model to be tolerant across versions.
            allowed = set(model.model_fields.keys())
            filtered = {k: v for k, v in fixed.items() if k in allowed}
            obj = model(**filtered)
            session.add(obj)
            counts[name] += 1
        session.flush()
    session.commit()
    return ImportResult(counts=counts, workspace_id=target_workspace_id, remapped=remap_needed)
