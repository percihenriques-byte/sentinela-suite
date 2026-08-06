"""Generic workspace-scoped CRUD helpers.

Every domain entity in this system inherits from WorkspaceScopedModel and carries
`workspace_id` + `deleted_at`. Rather than duplicating filter clauses in every
route, callers use these helpers so tenant isolation and soft-delete are enforced
in exactly one place.
"""
from datetime import datetime, timezone
from typing import Any, Sequence, TypeVar
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, SQLModel, select
from sqlmodel.sql.expression import SelectOfScalar

T = TypeVar("T", bound=SQLModel)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def scoped_query(model: type[T], workspace_id: UUID, include_deleted: bool = False) -> SelectOfScalar[T]:
    stmt = select(model).where(model.workspace_id == workspace_id)
    if not include_deleted:
        stmt = stmt.where(model.deleted_at.is_(None))
    return stmt


def count_from(session: Session, stmt: SelectOfScalar) -> int:
    """Return the row count for a SELECT (safe to call before pagination is applied)."""
    return int(session.exec(select(func.count()).select_from(stmt.subquery())).one())


def count_scoped(session: Session, model: type[T], workspace_id: UUID, include_deleted: bool = False) -> int:
    stmt = select(func.count()).select_from(model).where(model.workspace_id == workspace_id)
    if not include_deleted:
        stmt = stmt.where(model.deleted_at.is_(None))
    return int(session.exec(stmt).one())


def get_or_404(session: Session, model: type[T], workspace_id: UUID, obj_id: UUID) -> T:
    obj = session.exec(scoped_query(model, workspace_id).where(model.id == obj_id)).first()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return obj


def like_escape(query: str) -> str:
    """Escape LIKE/ILIKE wildcards in user-provided search input.

    Without this, a user searching for `_` matches every single character
    and a search for `%` returns the entire table. Callers still wrap the
    result in `%...%` themselves; the ilike() call must be paired with
    `escape="\\"` for the escapes to take effect.
    """
    if query is None:
        return ""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def verify_scoped_exists(
    session: Session,
    model: type[T],
    workspace_id: UUID,
    obj_id: UUID | None,
    *,
    label: str | None = None,
) -> None:
    """Cheap existence + tenant check for caller-supplied foreign keys.

    Prevents cross-workspace data stitching — a client could otherwise pass a
    UUID from workspace B into a POST/PATCH in workspace A and end up with a
    row referencing foreign data. Only queries the id column, so it's fast to
    call on every FK in a payload.

    Passing `obj_id=None` is a no-op so callers can validate optional fields
    unconditionally.
    """
    if obj_id is None:
        return
    stmt = select(model.id).where(
        model.id == obj_id,
        model.workspace_id == workspace_id,
        model.deleted_at.is_(None),
    )
    if session.exec(stmt).first() is None:
        name = label or model.__name__.lower()
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{name} not found")


def list_scoped(
    session: Session,
    model: type[T],
    workspace_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
    order_by: Any = None,
) -> Sequence[T]:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    stmt = scoped_query(model, workspace_id)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    else:
        stmt = stmt.order_by(model.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list(session.exec(stmt).all())


def create_scoped(session: Session, obj: T) -> T:
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def apply_updates(obj: T, updates: dict[str, Any], *, allowed: set[str]) -> T:
    for key, value in updates.items():
        if key not in allowed:
            continue
        if value is None and not _field_is_optional(obj, key):
            continue
        setattr(obj, key, value)
    obj.updated_at = _now()
    return obj


def _field_is_optional(obj: SQLModel, key: str) -> bool:
    """Return True iff the field's type annotation actually accepts None.

    Previous implementation used `is_required()` which returns False for ANY
    field with a default value, including required-but-defaulted booleans like
    `is_active: bool = Field(default=True)`. That let a PATCH request pass
    `is_active: null` and clobber the field with None on the way to a crash at
    commit. Now we check the annotation for a Union-with-None.
    """
    import types
    from typing import Union, get_args, get_origin

    field = obj.__class__.model_fields.get(key)
    if field is None:
        return True  # unknown key — skip in caller anyway
    ann = field.annotation
    origin = get_origin(ann)
    if origin in (Union,) or origin is getattr(types, "UnionType", None):
        return type(None) in get_args(ann)
    return False


def soft_delete(session: Session, obj: T) -> None:
    obj.deleted_at = _now()
    session.add(obj)
    session.commit()
