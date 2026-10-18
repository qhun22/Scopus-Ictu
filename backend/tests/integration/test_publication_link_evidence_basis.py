"""D-3 (PROMPT 09): approved lecturer links expose evidence_basis additively.

Reuses the A1 publication catalog fixture. Its APPROVED identities were created
without identity_evidence rows or a review, i.e. the "historical link with no
recorded evidence" case, which must never be presented as verified.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.publication import ScopusAuthor
from tests.integration.test_publication_api import (  # noqa: F401  (fixtures)
    authenticate,
    catalog,
    client,
    db_session,
)


def _links(client, authenticate, role: str = "ADMIN") -> list[dict]:
    authenticate(role)
    return client.get("/api/v1/publications/EID-2024-A").json()["approved_lecturer_links"]


def test_links_without_recorded_evidence_are_not_verified(client, authenticate, catalog) -> None:  # noqa: F811
    links = _links(client, authenticate)
    assert links, "fixture must have approved links"
    for link in links:
        assert link["link_status"] == "APPROVED"
        assert link["evidence_basis"]["level"] == "NO_RECORDED_EVIDENCE"
        assert link["evidence_basis"]["independently_verified"] is False
        assert link["review_decision"] is None
        assert "id" not in link and "identity_id" not in link  # no internal ids leak


def test_evidence_basis_reflects_identity_evidence_rows(client, authenticate, catalog, db_session) -> None:  # noqa: F811
    identity = db_session.scalar(
        select(LecturerScopusIdentity)
        .join(ScopusAuthor, ScopusAuthor.id == LecturerScopusIdentity.scopus_author_id)
        .where(ScopusAuthor.scopus_id == "1001", LecturerScopusIdentity.status == "APPROVED")
    )
    db_session.add(IdentityEvidence(
        id=uuid.uuid4(), identity_id=identity.id, evidence_type="DOI_EXACT", direction="SUPPORTS",
        confidence_score=None, algorithm_version="M2.7A-5", features={}, source_refs=[],
        evidence_fingerprint="a" * 64, created_at=datetime.now(UTC),
    ))
    db_session.commit()
    by_scopus = {link["scopus_id"]: link for link in _links(client, authenticate)}
    assert by_scopus["1001"]["evidence_basis"]["level"] == "PUBLICATION_SUPPORT"
    assert by_scopus["1001"]["evidence_basis"]["supporting_evidence_types"] == ["DOI_EXACT"]
    assert by_scopus["1001"]["evidence_basis"]["independently_verified"] is False
    assert by_scopus["1002"]["evidence_basis"]["level"] == "NO_RECORDED_EVIDENCE"


def test_lecturer_still_receives_no_links(client, authenticate, catalog) -> None:  # noqa: F811
    assert _links(client, authenticate, "LECTURER") == []
