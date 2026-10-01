"""Lecturer endpoints — M0 scaffold."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", summary="M0 healthcheck")
def ping() -> dict[str, str]:
    """M0 placeholder."""
    return {"status": "lecturers-stub", "milestone": "M0"}