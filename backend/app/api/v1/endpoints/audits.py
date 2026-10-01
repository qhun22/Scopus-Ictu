"""Audit endpoints — M0 scaffold.

ADR-003: read-only listing. Mutating endpoints are append-only (in M1+).
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", summary="M0 healthcheck")
def ping() -> dict[str, str]:
    """M0 placeholder."""
    return {"status": "audits-stub", "milestone": "M0"}