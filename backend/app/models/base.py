"""SQLAlchemy 2.x Declarative Base — M1.1 (frozen contract).

Owns the shared ORM infrastructure only:

    * DeclarativeBase subclass
    * MetaData singleton
    * Frozen naming convention from M1.0-A / FC-01

Per the original M1.1 directive §5, this module does NOT define generic
mixins such as ``id``, ``timestamps``, ``version``, ``is_active``, or
soft-delete helpers, because the M1.0-B freeze record explicitly varies
those properties per table. Centralizing them as mixins would either
hide contract drift or force a table to inherit semantics that the
frozen contract does not allow.

Per M1.0-A16/A17, the naming convention is::

    pk:  pk_%(table_name)s
    fk:  fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s
    uq:  uq_%(table_name)s_%(column_0_name)s
    ck:  ck_%(table_name)s_%(constraint_name)s
    ix:  ix_%(table_name)s_%(column_0_label)s

Per FC-01, when constructing ``CheckConstraint(..., name=...)`` the
semantic suffix from FC-01 is passed — never the already-expanded
``ck_<table>_<suffix>`` name.

Composite constraints / partial indexes are declared with explicit
``name=`` and are not produced by the auto-template.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


# Frozen naming convention (M1.0-A16/A17). Do not modify without
# reopening the M1.0-A contract.
NAMING_CONVENTION: dict[str, str] = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_label)s",
}


class Base(DeclarativeBase):
    """Declarative base for all M1.1 ORM models.

    The MetaData singleton binds the frozen naming convention so that
    every Constraint / Index declared via SQLAlchemy 2.x declarative
    helpers resolves to a deterministic physical name compatible with
    the future M1.2 Alembic migration.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
