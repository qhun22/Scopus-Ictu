"""Application entry point — M2.2 runtime implementation.

Wires FastAPI application with CORS middleware, settings, and v1 API routers.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Factory for the FastAPI application."""
    app = FastAPI(
        title="Scopus-Ictu API",
        description="Identity reconciliation pipeline between ICTU Repository and Scopus records.",
        version="0.1.0",
    )

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

    @app.get("/health", summary="Health check")
    def health() -> dict[str, str]:
        """Health check endpoint to verify backend service readiness."""
        return {"status": "ok", "app": "Scopus-Ictu API", "version": "0.1.0"}

    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()

__all__ = ["app"]