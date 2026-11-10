"""Why a position lands in the ADMIN review list, against synthetic data on in-memory SQLite."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.affiliation import PublicationAuthorAffiliationResolution
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor
from app.services.affiliation_override_service import list_needs_review
from tests.source_staging_fixtures import make_sqlite_engine

NOW = datetime(2026, 11, 9, 10, 0, tzinfo=UTC)
METHODS = {"VERIFIED": "ORCID_SCOPUS_ID_BRIDGE", "CORROBORATED": "POSITION_COUNT_NAME"}


@pytest.fixture
def db() -> Generator[Session, None, None]:
    with Session(make_sqlite_engine(), expire_on_commit=False) as session:
        yield session


def _position(db: Session) -> uuid.UUID:
    publication = Publication(
        id=uuid.uuid4(), eid="2-s2.0-1", title="T", title_normalized="t", version=1,
        created_at=NOW, updated_at=NOW,
    )
    author = ScopusAuthor(
        id=uuid.uuid4(), scopus_id="57000000001", preferred_name="A", created_at=NOW, updated_at=NOW
    )
    position = PublicationAuthor(
        id=uuid.uuid4(), publication_id=publication.id, scopus_author_id=author.id, author_order=1,
        created_at=NOW,
    )
    db.add_all([publication, author, position])
    db.flush()
    return position.id


def _resolution(db: Session, position: uuid.UUID, source: str, status: str, *,
                reason: str | None = None, age_days: int = 0) -> None:
    db.add(PublicationAuthorAffiliationResolution(
        id=uuid.uuid4(), publication_author_id=position, source_system=source,
        source_payload_sha256=f"{uuid.uuid4().int:064x}"[:64], link_status=status,
        link_method=METHODS.get(status), unresolved_reason=reason, evidence={},
        importer_version="test", created_at=NOW - timedelta(days=age_days), retrieved_at=NOW,
    ))
    db.flush()


@pytest.mark.parametrize("crossref,openalex,reason,kind", [
    ("VERIFIED", "CORROBORATED", None, "LOW_CONFIDENCE"),  # same person, two levels of trust
    ("VERIFIED", "UNRESOLVED", "NAME_MISMATCH", "CONFLICTING_SOURCES"),
    ("CORROBORATED", "CORROBORATED", None, "LOW_CONFIDENCE"),
    ("CORROBORATED", "UNRESOLVED", "NAME_MISMATCH", "LOW_CONFIDENCE"),
    ("CORROBORATED", "UNRESOLVED", "POSITION_CLAIMED_BY_OTHER_ID", "CONFLICTING_SOURCES"),
    ("UNRESOLVED", "UNRESOLVED", "NO_EXTERNAL_WORK", "UNRESOLVED"),
])
def test_reason_kind(db: Session, crossref, openalex, reason, kind) -> None:
    position = _position(db)
    _resolution(db, position, "crossref", crossref,
                reason=None if crossref != "UNRESOLVED" else reason)
    _resolution(db, position, "openalex", openalex,
                reason=None if openalex != "UNRESOLVED" else reason)

    items, total = list_needs_review(db)

    assert total == 1 and items[0].reason_kind == kind


def test_verified_by_every_source_is_not_listed(db: Session) -> None:
    position = _position(db)
    _resolution(db, position, "crossref", "VERIFIED")

    assert list_needs_review(db) == ([], 0)


def test_only_the_current_resolution_of_each_source_counts(db: Session) -> None:
    position = _position(db)
    _resolution(db, position, "crossref", "VERIFIED")
    _resolution(db, position, "openalex", "UNRESOLVED", reason="NAME_MISMATCH", age_days=3)
    _resolution(db, position, "openalex", "CORROBORATED")

    items, _ = list_needs_review(db)

    assert items[0].reason_kind == "LOW_CONFIDENCE"
    assert [(s["source_system"], s["link_status"]) for s in items[0].resolution_summaries] == [
        ("crossref", "VERIFIED"), ("openalex", "CORROBORATED"),
    ]
