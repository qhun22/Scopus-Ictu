"""v1 router aggregator — M0 scaffold.

Wires endpoint modules under a single APIRouter.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    audits,
    auth,
    authors,
    imports,
    lecturers,
    matching,
    publications,
    reviews,
)

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(lecturers.router, prefix="/lecturers", tags=["lecturers"])
router.include_router(imports.router, prefix="/imports", tags=["imports"])
router.include_router(publications.router, prefix="/publications", tags=["publications"])
router.include_router(authors.router, prefix="/authors", tags=["authors"])
router.include_router(matching.router, prefix="/matching", tags=["matching"])
router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
router.include_router(audits.router, prefix="/audits", tags=["audits"])