"""Application entry point — M2.2/M2.5 runtime implementation.

Wires FastAPI application with CORS middleware, settings, and v1 API routers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.exceptions import APIError, api_error_handler
from app.services.scopus_import_service import recover_interrupted_imports

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Factory for the FastAPI application."""

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if getattr(application.state, "import_recovery_enabled", True):
            try:
                recovered = recover_interrupted_imports()
                if recovered:
                    logger.warning("Recovered %s interrupted Scopus import job(s).", recovered)
            except Exception:
                logger.exception("Could not recover interrupted Scopus imports at startup.")
        yield

    app = FastAPI(
        title="Scopus-Ictu API",
        description="Identity reconciliation pipeline between ICTU Repository and Scopus records.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.import_recovery_enabled = True

    # CORS configuration with credentials enabled for HttpOnly cookie exchange
    origins = settings.cors_origins_list
    if not origins:
        origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(APIError, api_error_handler)

    @app.get("/health", summary="Health check")
    def health() -> dict[str, str]:
        """Health check endpoint to verify backend service readiness."""
        return {"status": "ok", "app": "Scopus-Ictu API", "version": "0.1.0"}

    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()

__all__ = ["app"]
