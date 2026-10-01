"""SQLAlchemy declarative base.

TODO(M1): wire concrete metadata, naming conventions, and common mixins.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    TODO(M1): add naming conventions, audit columns, and common mixins.
    """

    pass