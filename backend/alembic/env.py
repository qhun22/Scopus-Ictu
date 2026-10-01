"""Alembic environment for the frozen M1.2 schema migration.

Both online and offline migration modes use the PostgreSQL URL supplied by
the application's authorized settings object. Configuration failures are
reported explicitly and never fall back to a connection placeholder.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

# Resolve ``app.*`` from the backend directory regardless of the caller's CWD.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models import Base  # noqa: E402

target_metadata = Base.metadata
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_url() -> str:
    """Return the configured PostgreSQL URL or fail closed."""
    try:
        from app.core.config import settings

        url = make_url(settings.database_url)
    except Exception:
        raise RuntimeError(
            "MIGRATION_CONFIG_GAP: authorized application configuration "
            "could not provide a database URL"
        ) from None

    if url.get_backend_name() != "postgresql":
        raise RuntimeError(
            "MIGRATION_CONFIG_GAP: configured database URL must use PostgreSQL"
        )

    return url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    """Render migration SQL without opening a database connection."""
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations through an application-configured PostgreSQL engine."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _resolve_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
