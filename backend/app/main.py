"""Application entry point — M0 skeleton.

M0 verifies:
  - uvicorn app.main:app starts without import errors
  - /docs loads
  - v1 router skeletons appear
No business logic.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.router import router as v1_router


def create_app() -> FastAPI:
    """Factory for the FastAPI application (M0 stub)."""
    # TODO(M1): wire Pydantic settings, CORS, middleware.
    app = FastAPI(
        title="Scopus-Ictu API",
        description="Identity reconciliation pipeline between ICTU Repository and Scopus records.",
        version="0.1.0",
    )
    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()

# Convenience for `uvicorn app.main:app`
__all__ = ["app"]