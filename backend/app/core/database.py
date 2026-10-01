"""Database session management — M0 scaffold.

M0: engine/session factory signatures only.
TODO(M1): real SQLAlchemy engine creation from app.core.config.settings.
"""

from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy.orm import Session

# TODO(M1): replace with real engine from app.core.config.
_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the SQLAlchemy engine.

    TODO(M1): instantiate from settings.database_url.
    """
    raise NotImplementedError("Database engine not configured in M0.")


def get_session() -> Session:
    """Yield a SQLAlchemy session (M0 stub).

    TODO(M1): dependency-inject a scoped session factory.
    """
    raise NotImplementedError("Session factory not configured in M0.")


def init_db() -> None:
    """Create all tables defined in app.models (M0 stub).

    TODO(M1): call metadata.create_all(engine) after models are wired.
    """
    raise NotImplementedError("init_db() is not implemented in M0.")