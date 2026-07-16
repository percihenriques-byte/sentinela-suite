from collections.abc import Iterator
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.core.config import get_settings

_settings = get_settings()
_kwargs: dict = {"echo": False}
if _settings.database_url.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}
    # For in-memory SQLite, all connections must share the same DB.
    if ":memory:" in _settings.database_url:
        _kwargs["poolclass"] = StaticPool

engine = create_engine(_settings.database_url, **_kwargs)


def init_db() -> None:
    # Import models so SQLModel metadata sees them before create_all.
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
