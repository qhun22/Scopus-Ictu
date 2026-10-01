"""Alembic environment — M0 scaffold only.

The first real migration is intentionally NOT generated in M0.
M1 will fill in `run_migrations_online` against the real metadata.
"""

from __future__ import annotations

# TODO(M1): wire this module to app.core.config and app.models.base.metadata.
# For M0, we only keep the structural skeleton so Alembic imports cleanly.


def run_migrations_offline() -> None:
    """M0 stub.

    TODO(M1): generate SQL scripts with `url = config.get_main_option("sqlalchemy.url")`.
    """
    raise NotImplementedError("Alembic offline mode is not implemented in M0.")


def run_migrations_online() -> None:
    """M0 stub.

    TODO(M1): create an engine from app.core.config and run migrations against
    the SQLAlchemy metadata produced by app.models.
    """
    raise NotImplementedError("Alembic online mode is not implemented in M0.")


if __name__ == "__main__":
    # M0: explicit no-op. Real entrypoint wired in M1 via env.py -> alembic.
    pass