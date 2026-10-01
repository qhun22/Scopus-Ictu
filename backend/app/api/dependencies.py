"""FastAPI dependency providers — M0 scaffold."""

from __future__ import annotations


def get_db_session():
    """Dependency that yields a SQLAlchemy session (M0 stub)."""
    raise NotImplementedError("get_db_session not wired in M0.")


def get_current_user():
    """Dependency that returns the authenticated user (M0 stub)."""
    raise NotImplementedError("get_current_user not wired in M0.")