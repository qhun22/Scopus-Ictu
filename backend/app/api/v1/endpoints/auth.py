"""Auth endpoints — M0 scaffold."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", summary="M0 healthcheck")
def ping() -> dict[str, str]:
    """M0 placeholder. Returns a static status."""
    return {"status": "auth-stub", "milestone": "M0"}