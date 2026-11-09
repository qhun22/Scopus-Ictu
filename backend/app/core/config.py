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

from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BACKEND_DIR = Path(__file__).resolve().parents[2]
LOCAL_ENV_FILE = BACKEND_DIR / ".env"


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
    db_user: str = Field(..., validation_alias="DB_USER")
    db_password: str = Field(..., validation_alias="DB_PASSWORD")
    db_host: str = Field(..., validation_alias="DB_HOST")
    db_port: int = Field(5432, validation_alias="DB_PORT")
    db_name: str = Field(..., validation_alias="DB_NAME")
    db_driver: str = Field("postgresql+psycopg2", validation_alias="DB_DRIVER")

    # ------------------------------------------------------------------
    # CORS — comma-separated list sourced from environment.
    # MUST NOT be hard-coded origins in source.
    # ------------------------------------------------------------------
    backend_cors_origins: str = Field(..., validation_alias="BACKEND_CORS_ORIGINS")

    # ------------------------------------------------------------------
    # Security — JWT secret key and token expiration.
    # ------------------------------------------------------------------
    secret_key: str = Field(..., validation_alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(
        60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # ------------------------------------------------------------------
    # Environment flag — local | dev | prod.
    # ------------------------------------------------------------------
    environment: str = Field(..., validation_alias="ENVIRONMENT")

    # ------------------------------------------------------------------
    # Google Sign-In (OAuth 2.0 authorization code flow). Optional: when
    # the client id/secret are unset, the /auth/google/* endpoints report
    # "not configured" instead of failing at process start.
    # ------------------------------------------------------------------
    google_client_id: str | None = Field(None, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(None, validation_alias="GOOGLE_CLIENT_SECRET")
    # Comma-separated front-end origins this backend is reachable behind
    # (each is proxied at /api, so the redirect_uri is "<origin>/api/v1/auth/google/callback").
    # Must exactly match the "Authorized redirect URIs" configured in Google Cloud Console.
    google_oauth_allowed_origins: str = Field(
        "", validation_alias="GOOGLE_OAUTH_ALLOWED_ORIGINS"
    )
    google_allowed_email_domain: str = Field(
        "ictu.edu.vn", validation_alias="GOOGLE_ALLOWED_EMAIL_DOMAIN"
    )

    # ------------------------------------------------------------------
    # Offline file paths (never HTTP URLs).
    # ------------------------------------------------------------------
    dspace_snapshot_path: str = Field(
        "./data/snapshots/", validation_alias="DSPACE_SNAPSHOT_PATH"
    )
    scopus_raw_dir: str = Field(
        "./data/raw_scopus/", validation_alias="SCOPUS_RAW_DIR"
    )
    scopus_import_max_bytes: int = Field(
        20 * 1024 * 1024,
        ge=1,
        validation_alias="SCOPUS_IMPORT_MAX_BYTES",
    )
    scopus_import_batch_size: int = Field(
        100,
        ge=1,
        le=10_000,
        validation_alias="SCOPUS_IMPORT_BATCH_SIZE",
    )
    scopus_normalization_batch_size: int = Field(
        500,
        ge=1,
        le=50_000,
        validation_alias="SCOPUS_NORMALIZATION_BATCH_SIZE",
    )

    # ------------------------------------------------------------------
    # Author-affiliation source bundle (offline).  Fixed by the operator; the
    # ADMIN workflow never accepts a path from a request.  Optional: without it
    # the workflow reports "source not configured" and nothing else breaks.
    # ------------------------------------------------------------------
    affiliation_source_dir: str | None = Field(None, validation_alias="AFFILIATION_SOURCE_DIR")

    # ------------------------------------------------------------------
    # ICTU Craw known-publication source bundle (offline).  Fixed by the
    # operator; the ADMIN workflow never accepts a path from a request.
    # Optional: without it the ingestion endpoint reports "not configured".
    # ------------------------------------------------------------------
    craw_source_dir: str | None = Field(None, validation_alias="CRAW_SOURCE_DIR")

    # ICTU "Scopus account merge guide" saved as JSON by the operator (a review hint, read-only).
    # Optional: without it the reviewer simply gets no hint. Never a path from a request.
    merge_guide_file: str | None = Field(None, validation_alias="MERGE_GUIDE_FILE")

    # ------------------------------------------------------------------
    # Online affiliation enrichment (Priority 1).  Each run writes its own
    # bundle under this directory (never the offline AFFILIATION_SOURCE_DIR
    # above, never a path from a request). Optional: without it the
    # enrichment endpoint reports "not configured".
    # ------------------------------------------------------------------
    affiliation_online_cache_dir: str | None = Field(None, validation_alias="AFFILIATION_ONLINE_CACHE_DIR")
    # 1000, not 300: a first-time bulk import (or several incremental ones before
    # anyone runs enrichment) easily exceeds a few hundred publications, and
    # `_dois_to_enrich` already orders gapped publications first, so a run that
    # still falls short of the total makes real progress rather than looping on
    # the same publications — this cap is a safety margin against pathologically
    # large one-off imports, not the primary defence against unbounded growth.
    affiliation_online_max_dois_per_run: int = Field(
        1000, ge=1, le=5000, validation_alias="AFFILIATION_ONLINE_MAX_DOIS_PER_RUN"
    )

    model_config = SettingsConfigDict(
        env_file=str(LOCAL_ENV_FILE),
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

    @computed_field  # type: ignore[misc]
    @property
    def google_oauth_allowed_origins_list(self) -> list[str]:
        """Parse the comma-separated Google OAuth origin allow-list."""
        return [
            origin.strip().rstrip("/")
            for origin in self.google_oauth_allowed_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
