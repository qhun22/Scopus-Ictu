"""Focused M2.8-A1 tests for the approved identity read projection."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit import AuditEvent
from app.models.base import Base
from app.models.candidate import LecturerScopusCandidateReview
from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import (
    Publication,
    PublicationAuthor,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.lecturer_scopus_projection import LecturerScopusProjectionService


@pytest.fixture(autouse=True)
def projection_schema(isolated_db_engine: Engine | None) -> None:
    if isolated_db_engine is None:
        pytest.skip("No isolated test database available.")
    Base.metadata.create_all(bind=isolated_db_engine)


@pytest.fixture
def projection_session(isolated_db_engine: Engine | None):
    if isolated_db_engine is None:
        pytest.skip("No isolated test database available.")
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=isolated_db_engine,
    )
    session = session_factory()
    transaction = session.begin()
    try:
        yield session
    finally:
        if transaction.is_active:
            transaction.rollback()
        session.close()


def _lecturer(*, full_name: str = "Test Lecturer") -> Lecturer:
    lecturer_id = uuid.uuid4()
    return Lecturer(
        id=lecturer_id,
        staff_code=f"CB-{lecturer_id.hex[:8]}",
        full_name=full_name,
        full_name_normalized=full_name.casefold(),
        email=f"{lecturer_id.hex[:8]}@ictu.edu.vn",
        academic_rank="TS",
        academic_degree="PhD",
        position="Lecturer",
        department="Software Engineering",
        faculty="Information Technology",
        repository_profile_url=f"https://repository.example/{lecturer_id}",
        orcid="0000-0002-1825-0097",
        is_active=True,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _author(*, scopus_id: str | None = None, name: str = "Test Author") -> ScopusAuthor:
    author_id = uuid.uuid4()
    return ScopusAuthor(
        id=author_id,
        scopus_id=scopus_id or author_id.hex[:11],
        preferred_name=name,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _identity(
    lecturer: Lecturer,
    author: ScopusAuthor,
    *,
    status: str = "APPROVED",
) -> LecturerScopusIdentity:
    now = datetime.now(UTC)
    return LecturerScopusIdentity(
        id=uuid.uuid4(),
        lecturer_id=lecturer.id,
        scopus_author_id=author.id,
        status=status,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _publication(
    *,
    eid: str,
    year: int | None,
    cited_by_count: int | None,
) -> Publication:
    return Publication(
        id=uuid.uuid4(),
        eid=eid,
        doi=None,
        title=f"Publication {eid}",
        title_normalized=f"publication {eid}",
        source_title="ICTU Journal",
        year=year,
        cited_by_count=cited_by_count,
        document_type="Article",
        publication_stage="Final",
        open_access_status="Open",
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _link(
    publication: Publication,
    author: ScopusAuthor,
    *,
    author_order: int,
) -> PublicationAuthor:
    return PublicationAuthor(
        id=uuid.uuid4(),
        publication_id=publication.id,
        scopus_author_id=author.id,
        author_order=author_order,
        created_at=datetime.now(UTC),
    )


def _evidence(identity: LecturerScopusIdentity, evidence_type: str) -> IdentityEvidence:
    fingerprint = hashlib.sha256(
        f"{identity.id}:{evidence_type}".encode("utf-8")
    ).hexdigest()
    return IdentityEvidence(
        id=uuid.uuid4(),
        identity_id=identity.id,
        evidence_type=evidence_type,
        direction="SUPPORTS",
        confidence_score=None,
        algorithm_version="test-internal-version",
        features={"internal": "not exposed"},
        source_refs=[{"internal": "not exposed"}],
        evidence_fingerprint=fingerprint,
        created_at=datetime.now(UTC),
    )


def test_t01_existing_lecturer_profile(projection_session: Session) -> None:
    lecturer = _lecturer(full_name="Profile Lecturer")
    projection_session.add(lecturer)
    projection_session.flush()

    result = LecturerScopusProjectionService(projection_session).get_lecturer_profile(
        lecturer.id
    )

    assert result is not None
    assert result.model_dump() == {
        "lecturer_id": lecturer.id,
        "full_name": "Profile Lecturer",
        "staff_code": lecturer.staff_code,
        "email": lecturer.email,
        "academic_rank": "TS",
        "academic_degree": "PhD",
        "position": "Lecturer",
        "department": "Software Engineering",
        "faculty": "Information Technology",
        "repository_profile_url": lecturer.repository_profile_url,
        "orcid": lecturer.orcid,
    }


def test_t02_no_approved_identity(projection_session: Session) -> None:
    lecturer = _lecturer()
    projection_session.add(lecturer)
    projection_session.flush()
    service = LecturerScopusProjectionService(projection_session)

    identities = service.get_approved_identity_summaries(lecturer.id)
    publications = service.get_lecturer_publications(lecturer.id)
    aggregates = service.get_lecturer_publication_aggregates(lecturer.id)

    assert identities == []
    assert publications.items == []
    assert publications.total == 0
    assert aggregates.model_dump() == {
        "total_publications": 0,
        "publication_count_by_year": {},
        "unknown_year_count": 0,
        "known_citation_sum": 0,
        "citation_unknown_publication_count": 0,
        "approved_identity_count": 0,
    }


def test_t03_non_approved_identities_excluded(projection_session: Session) -> None:
    lecturer = _lecturer()
    authors = [_author(name=f"Author {status}") for status in ("CANDIDATE", "REJECTED", "REVOKED")]
    identities = [
        _identity(lecturer, author, status=status)
        for author, status in zip(authors, ("CANDIDATE", "REJECTED", "REVOKED"))
    ]
    projection_session.add(lecturer)
    projection_session.add_all(authors)
    projection_session.flush()
    projection_session.add_all(identities)
    projection_session.flush()

    result = LecturerScopusProjectionService(
        projection_session
    ).get_approved_identity_summaries(lecturer.id)

    assert result == []


def test_t04_single_approved_identity(projection_session: Session) -> None:
    lecturer = _lecturer()
    author = _author(scopus_id="12345678901", name="Approved Author")
    identity = _identity(lecturer, author)
    raw_import = ScopusImport(
        id=uuid.uuid4(),
        file_name="projection.csv",
        file_sha256="a" * 64,
        status="APPLIED",
        total_records=1,
        valid_records=1,
        invalid_records=0,
    )
    raw_record = RawScopusRecord(
        id=uuid.uuid4(),
        import_id=raw_import.id,
        row_number=1,
        row_hash="b" * 64,
        eid_raw="2-s2.0-test",
        raw_payload={"eid": "2-s2.0-test"},
        validation_status="VALID",
    )
    projection_session.add_all([lecturer, author, raw_import])
    projection_session.flush()
    projection_session.add_all([raw_record, identity])
    projection_session.flush()
    projection_session.add(_evidence(identity, "NAME_SIMILARITY"))
    projection_session.add(
        ScopusAuthorNameVariant(
            id=uuid.uuid4(),
            scopus_author_id=author.id,
            variant_type="AUTHOR_DISPLAY",
            variant_name="Approved A",
            variant_name_normalized="approved a",
            first_seen_raw_record_id=raw_record.id,
            created_at=datetime.now(UTC),
        )
    )
    projection_session.flush()

    result = LecturerScopusProjectionService(
        projection_session
    ).get_approved_identity_summaries(lecturer.id)

    assert len(result) == 1
    assert result[0].scopus_id == "12345678901"
    assert result[0].preferred_name == "Approved Author"
    assert result[0].name_variants == ["Approved A"]
    assert result[0].evidence[0].evidence_type == "NAME_SIMILARITY"


def test_t05_multiple_approved_identities(projection_session: Session) -> None:
    lecturer = _lecturer()
    author_a = _author(scopus_id="10000000001", name="Author A")
    author_b = _author(scopus_id="10000000002", name="Author B")
    projection_session.add_all([lecturer, author_a, author_b])
    projection_session.flush()
    projection_session.add_all(
        [_identity(lecturer, author_a), _identity(lecturer, author_b)]
    )
    projection_session.flush()

    result = LecturerScopusProjectionService(
        projection_session
    ).get_approved_identity_summaries(lecturer.id)

    assert [item.scopus_id for item in result] == ["10000000001", "10000000002"]


def test_t06_identity_evidence_safe_fields(projection_session: Session) -> None:
    lecturer = _lecturer()
    author = _author()
    identity = _identity(lecturer, author)
    projection_session.add_all([lecturer, author])
    projection_session.flush()
    projection_session.add(identity)
    projection_session.flush()
    projection_session.add(_evidence(identity, "DOI_EXACT"))
    projection_session.flush()

    item = LecturerScopusProjectionService(
        projection_session
    ).get_approved_identity_summaries(lecturer.id)[0]
    evidence_payload = item.evidence[0].model_dump()

    assert set(evidence_payload) == {"evidence_type", "direction", "created_at"}
    assert evidence_payload["evidence_type"] == "DOI_EXACT"


def test_t07_publication_join(projection_session: Session) -> None:
    lecturer = _lecturer()
    author = _author()
    identity = _identity(lecturer, author)
    publication = _publication(eid="EID-1", year=2024, cited_by_count=3)
    projection_session.add_all([lecturer, author, publication])
    projection_session.flush()
    projection_session.add(identity)
    projection_session.flush()
    projection_session.add(_link(publication, author, author_order=1))
    projection_session.flush()

    result = LecturerScopusProjectionService(
        projection_session
    ).get_lecturer_publications(lecturer.id)

    assert result.total == 1
    assert result.items[0].eid == "EID-1"
    assert result.items[0].linked_author_orders == [1]


def _seed_publication_set(session: Session) -> tuple[Lecturer, list[Publication]]:
    lecturer = _lecturer()
    author_a = _author(scopus_id="20000000001", name="Author A")
    author_b = _author(scopus_id="20000000002", name="Author B")
    identity_a = _identity(lecturer, author_a)
    identity_b = _identity(lecturer, author_b)
    publication_a = _publication(eid="EID-A", year=2024, cited_by_count=4)
    publication_b = _publication(eid="EID-B", year=2024, cited_by_count=None)
    publication_c = _publication(eid="EID-C", year=None, cited_by_count=6)
    session.add_all(
        [lecturer, author_a, author_b, publication_a, publication_b, publication_c]
    )
    session.flush()
    session.add_all([identity_a, identity_b])
    session.flush()
    session.add_all(
        [
            _link(publication_a, author_a, author_order=1),
            _link(publication_a, author_b, author_order=2),
            _link(publication_b, author_a, author_order=1),
            _link(publication_c, author_b, author_order=1),
        ]
    )
    session.flush()
    return lecturer, [publication_a, publication_b, publication_c]


def test_t08_overlapping_publication_dedup(projection_session: Session) -> None:
    lecturer, _publications = _seed_publication_set(projection_session)

    result = LecturerScopusProjectionService(
        projection_session
    ).get_lecturer_publications(lecturer.id)

    assert result.total == 3
    assert len(result.items) == 3
    assert result.items[0].eid == "EID-A"
    assert result.items[0].linked_author_orders == [1, 2]


def test_t09_publication_ordering(projection_session: Session) -> None:
    lecturer, _publications = _seed_publication_set(projection_session)

    result = LecturerScopusProjectionService(
        projection_session
    ).get_lecturer_publications(lecturer.id)

    assert [item.eid for item in result.items] == ["EID-A", "EID-B", "EID-C"]


def test_t10_pagination_distinct_total(projection_session: Session) -> None:
    lecturer, _publications = _seed_publication_set(projection_session)
    service = LecturerScopusProjectionService(projection_session)

    first = service.get_lecturer_publications(lecturer.id, page=1, page_size=1)
    second = service.get_lecturer_publications(lecturer.id, page=2, page_size=1)

    assert first.total == 3
    assert second.total == 3
    assert [item.eid for item in first.items + second.items] == ["EID-A", "EID-B"]


def test_t11_null_year(projection_session: Session) -> None:
    lecturer, _publications = _seed_publication_set(projection_session)

    aggregates = LecturerScopusProjectionService(
        projection_session
    ).get_lecturer_publication_aggregates(lecturer.id)

    assert aggregates.publication_count_by_year == {2024: 2}
    assert aggregates.unknown_year_count == 1


def test_t12_null_citation(projection_session: Session) -> None:
    lecturer, _publications = _seed_publication_set(projection_session)

    aggregates = LecturerScopusProjectionService(
        projection_session
    ).get_lecturer_publication_aggregates(lecturer.id)

    assert aggregates.known_citation_sum == 10
    assert aggregates.citation_unknown_publication_count == 1


def test_t13_known_citations(projection_session: Session) -> None:
    lecturer, _publications = _seed_publication_set(projection_session)

    aggregates = LecturerScopusProjectionService(
        projection_session
    ).get_lecturer_publication_aggregates(lecturer.id)

    assert aggregates.total_publications == 3
    assert aggregates.approved_identity_count == 2
    assert aggregates.known_citation_sum == 10


def test_t14_approved_identity_with_zero_publications(projection_session: Session) -> None:
    lecturer = _lecturer()
    author = _author()
    projection_session.add_all([lecturer, author])
    projection_session.flush()
    projection_session.add(_identity(lecturer, author))
    projection_session.flush()
    service = LecturerScopusProjectionService(projection_session)

    publications = service.get_lecturer_publications(lecturer.id)
    aggregates = service.get_lecturer_publication_aggregates(lecturer.id)

    assert publications.items == []
    assert publications.total == 0
    assert aggregates.approved_identity_count == 1
    assert aggregates.total_publications == 0


def test_t15_read_only(projection_session: Session) -> None:
    lecturer, _publications = _seed_publication_set(projection_session)
    author = _author()
    identity = _identity(lecturer, author)
    projection_session.add(author)
    projection_session.flush()
    projection_session.add(identity)
    projection_session.flush()
    projection_session.add(_evidence(identity, "NAME_SIMILARITY"))
    projection_session.flush()

    tracked_tables = (
        (LecturerScopusIdentity, "lecturer_scopus_identities"),
        (IdentityEvidence, "identity_evidence"),
        (LecturerScopusCandidateReview, "lecturer_scopus_candidate_reviews"),
        (AuditEvent, "audit_events"),
    )

    before = {
        table_name: projection_session.scalar(select(func.count()).select_from(model))
        for model, table_name in tracked_tables
    }
    service = LecturerScopusProjectionService(projection_session)
    service.get_approved_identity_summaries(lecturer.id)
    service.get_lecturer_publications(lecturer.id, page=1, page_size=2)
    service.get_lecturer_publication_aggregates(lecturer.id)
    after = {
        table_name: projection_session.scalar(select(func.count()).select_from(model))
        for model, table_name in tracked_tables
    }

    assert after == before
    assert projection_session.execute(text("SELECT 1")).scalar_one() == 1
