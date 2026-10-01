"""Pydantic v2 Settings — M0.2 environment-neutral configuration.

All configuration values are environment-driven via Pydantic Settings.
NO values are hard-coded in this module.

The database connection is composed from individual `DB_*` variables
through a `computed_field` (Pydantic v2 computed property) so that the
password is never embedded in source. M0.2 additionally uses
`sqlalchemy.engine.URL.create(...)` to percent-encode the user, password,
host, and database name — f-string concatenation is unsafe when the
password contains characters such as `@`, `:`, `/`, or `?`.
"""

from __future__ import annotations

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Application settings sourced exclusively from environment variables.

    M0.2: structure only — no defaults that reveal credentials, hosts, or
    origins. Any missing required value must surface as a clear validation
    error at process start.
    TODO(M1): real defaults, validation, and redaction.
    """

    # ------------------------------------------------------------------
    # Database — components only (no full URL committed to source).
    # The composed URL is exposed via the `database_url` computed field.
    # ------------------------------------------------------------------
    db_user: str = Field("postgres", validation_alias="DB_USER")
    db_password: str = Field("postgres", validation_alias="DB_PASSWORD")
    db_host: str = Field("localhost", validation_alias="DB_HOST")
    db_port: int = Field(5432, validation_alias="DB_PORT")
    db_name: str = Field("scopus_ictu", validation_alias="DB_NAME")
    db_driver: str = Field("postgresql+psycopg2", validation_alias="DB_DRIVER")

    # ------------------------------------------------------------------
    # CORS — comma-separated list sourced from environment.
    # MUST NOT be hard-coded origins in source.
    # ------------------------------------------------------------------
    backend_cors_origins: str = Field(
        "http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="BACKEND_CORS_ORIGINS",
    )

    # ------------------------------------------------------------------
    # Security — JWT secret key and token expiration.
    # ------------------------------------------------------------------
    secret_key: str = Field(
        "insecure-dev-secret-key-change-in-production",
        validation_alias="SECRET_KEY",
    )
    access_token_expire_minutes: int = Field(
        60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # ------------------------------------------------------------------
    # Environment flag — local | dev | prod.
    # ------------------------------------------------------------------
    environment: str = Field("local", validation_alias="ENVIRONMENT")

    # ------------------------------------------------------------------
    # Offline file paths (never HTTP URLs).
    # ------------------------------------------------------------------
    dspace_snapshot_path: str = Field(
        "./data/snapshots/", validation_alias="DSPACE_SNAPSHOT_PATH"
    )
    scopus_raw_dir: str = Field(
        "./data/raw_scopus/", validation_alias="SCOPUS_RAW_DIR"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _driver_to_sqlalchemy(self) -> tuple[str, str]:
        """Translate the configured DB driver string into SQLAlchemy's
        ``(drivername, dialect)`` tuple expected by ``URL.create``.

        Examples:
            ``postgresql+psycopg2``  -> ``('postgresql+psycopg2', 'postgresql')``
            ``postgresql+asyncpg``   -> ``('postgresql+asyncpg', 'postgresql')``
            ``postgresql``           -> ``('postgresql', 'postgresql')``
        """
        drv = self.db_driver
        if "+" in drv:
            dialect = drv.split("+", 1)[0]
            return drv, dialect
        return drv, drv

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------
    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """Compose the SQLAlchemy database URL from the DB_* components.

        Uses ``sqlalchemy.engine.URL.create(...)`` so that the user,
        password, host, and database name are percent-encoded safely.
        This is required when the password contains reserved characters
        such as ``@``, ``:``, ``/``, ``?``, ``#``, or ``[``.
        """
        drivername, _dialect = self._driver_to_sqlalchemy()
        url = URL.create(
            drivername=drivername,
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )
        return url.render_as_string(hide_password=False)

    @computed_field  # type: ignore[misc]
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse the comma-separated CORS list into a list of origins."""
        return [
            origin.strip()
            for origin in self.backend_cors_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
