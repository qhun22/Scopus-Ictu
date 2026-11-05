"""ADMIN-only read shape of one affiliation override (shared by the affiliation workflow
endpoints and the ``/publications/affiliation-gaps`` list)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class OverrideRead(BaseModel):
    id: uuid.UUID
    publication_author_id: uuid.UUID
    affiliation_text: str
    confidence: str
    status: str
    evidence_url: str
    reason: str
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    revoked_by_user_id: uuid.UUID | None
    revoked_at: str | None
    version: int
    created_at: str
    updated_at: str


def override_to_read(row) -> OverrideRead:
    """ORM ``PublicationAuthorAffiliationOverride`` -> ``OverrideRead``."""

    return OverrideRead(
        id=row.id,
        publication_author_id=row.publication_author_id,
        affiliation_text=row.affiliation_text,
        confidence=row.confidence,
        status=row.status,
        evidence_url=row.evidence_url,
        reason=row.reason,
        created_by_user_id=row.created_by_user_id,
        updated_by_user_id=row.updated_by_user_id,
        revoked_by_user_id=row.revoked_by_user_id,
        revoked_at=row.revoked_at.isoformat() if row.revoked_at else None,
        version=row.version,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )
