"""Database session management — M2.2 runtime implementation.

Provides SQLAlchemy engine and scoped session lifecycle management for
FastAPI dependency injection and offline seed/test scripts.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the singleton SQLAlchemy engine configured from settings."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the singleton sessionmaker instance."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session per request."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def init_db(target_base: type[DeclarativeBase] | None = None) -> None:
    """Create tables on the current engine (primarily for testing/local setups)."""
    from app.models.base import Base
    import app.models  # noqa: F401 - ensure all ORM models are registered

    base = target_base or Base
    base.metadata.create_all(bind=get_engine())