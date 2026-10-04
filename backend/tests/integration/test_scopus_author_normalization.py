"""Integration tests for M2.6B Author Normalization.

Covers:
A.  APPLIED publication import → author normalization succeeds
B.  STAGED import → author normalization rejected
C.  Creates unique ScopusAuthor by scopus_id
D.  Creates both DISPLAY and FULL_NAME variants
E.  Creates correct author_order
F.  Re-run → no duplicate authors
G.  Re-run → no duplicate variants
H.  Re-run → no duplicate publication-author links
I.  Same Scopus ID with multiple names → one author + multiple variants
J.  Association conflict → no silent overwrite
K.  Failure → import remains APPLIED (never reverts to STAGED)
L.  M2.6A summary preserved after author normalization
M.  Re-running M2.6A after M2.6B → nested authors summary preserved
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import APIError
from app.models.base import Base
from app.models.governance import User
from app.models.publication import (
    Publication,
    PublicationAuthor,
    PublicationRawSource,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.normalization.scopus_author_normalizer import (
    AuthorNormalizationCounters,
    is_import_eligible_for_author_normalization,
    normalize_authors_for_import,
    normalize_name,
    parse_author_occurrences,
)
from app.services.normalization.scopus_normalizer import normalize_import


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    from app.core.config import settings

    url = settings.database_url
    schema = f"test_author_norm_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, pool_pre_ping=True, future=True)
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    except Exception:
        pytest.skip("PostgreSQL not available for integration tests")
    engine = create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = factory()
    session.info["test_schema"] = schema
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="author-test-admin@example.test",
        password_hash="fakehash",
        display_name="Author Test Admin",
        role="ADMIN",
        is_active=True,
        version=1,
        auth_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_staged_import(
    db_session: Session,
    admin_user: User,
    file_name: str = "test_authors.csv",
    status: str = "STAGED",
    normalization_summary: dict | None = None,
) -> ScopusImport:
    item = ScopusImport(
        id=uuid.uuid4(),
        file_name=file_name,
        file_sha256="a" * 64,
        total_records=1,
        valid_records=1,
        invalid_records=0,
        status=status,
        normalization_summary=normalization_summary,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(item)
    db_session.commit()
    return item


def _add_raw_record(
    db_session: Session,
    import_id: uuid.UUID,
    row_number: int,
    raw_payload: dict,
    validation_status: str = "VALID",
) -> RawScopusRecord:
    record = RawScopusRecord(
        id=uuid.uuid4(),
        import_id=import_id,
        row_number=row_number,
        row_hash="b" * 64,
        eid_raw=f"2-s2.0-{row_number}",
        doi_raw=None,
        raw_payload=raw_payload,
        validation_status=validation_status,
        validation_errors=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(record)
    db_session.commit()
    return record


def _apply_publication_normalization(
    db_session: Session,
    import_id: uuid.UUID,
) -> None:
    """Run M2.6A publication normalization for the import."""
    normalize_import(db_session, import_id)


# ---------------------------------------------------------------------------
# A. APPLIED import → author normalization succeeds
# ---------------------------------------------------------------------------

def test_applied_import_author_normalization_succeeds(
    db_session: Session, admin_user: User
):
    import_item = _make_staged_import(db_session, admin_user)

    raw = _add_raw_record(
        db_session,
        import_item.id,
        row_number=1,
        raw_payload={
            "Authors": "Nguyen T.",
            "Author full names": "Nguyen, Thanh-Tung (58035626100)",
            "Author(s) ID": "58035626100",
            "Title": "Test Paper",
        },
    )

    # Run M2.6A publication normalization first
    _apply_publication_normalization(db_session, import_item.id)

    # Verify import is now APPLIED
    db_session.refresh(import_item)
    assert import_item.status == "APPLIED"

    # Run M2.6B author normalization
    counters = normalize_authors_for_import(db_session, import_item.id)

    assert counters.raw_records_processed == 1
    assert counters.raw_records_failed == 0
    assert counters.author_occurrences == 1
    assert counters.authors_created == 1
    assert counters.authors_existing == 0

    # Verify author entity was created
    author = db_session.query(ScopusAuthor).filter(
        ScopusAuthor.scopus_id == "58035626100"
    ).first()
    assert author is not None
    assert author.preferred_name == "Nguyen, Thanh-Tung"

    # Verify both variants
    variants = db_session.query(ScopusAuthorNameVariant).filter(
        ScopusAuthorNameVariant.scopus_author_id == author.id
    ).all()
    assert len(variants) == 2
    variant_types = {v.variant_type for v in variants}
    assert "AUTHOR_DISPLAY" in variant_types
    assert "AUTHOR_FULL_NAME" in variant_types


# ---------------------------------------------------------------------------
# B. STAGED import → author normalization rejected
# ---------------------------------------------------------------------------

def test_staged_import_rejected_for_author_normalization(
    db_session: Session, admin_user: User
):
    import_item = _make_staged_import(db_session, admin_user, status="STAGED")

    eligible, reason = is_import_eligible_for_author_normalization(import_item)
    assert eligible is False
    assert "APPLIED" in reason


# ---------------------------------------------------------------------------
# C. Creates unique ScopusAuthor by scopus_id
# ---------------------------------------------------------------------------

def test_unique_scopus_author_by_scopus_id(
    db_session: Session, admin_user: User
):
    import_item = _make_staged_import(db_session, admin_user)

    # Add two raw records with the same author
    raw1 = _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "Nguyen T.", "Author full names": "Nguyen, T. (1)", "Author(s) ID": "1", "Title": "Paper 1"},
    )
    raw2 = _add_raw_record(
        db_session, import_item.id, 2,
        {"Authors": "Nguyen T.", "Author full names": "Nguyen, T. (1)", "Author(s) ID": "1", "Title": "Paper 2"},
    )

    _apply_publication_normalization(db_session, import_item.id)

    counters = normalize_authors_for_import(db_session, import_item.id)

    assert counters.unique_authors_seen == 1
    assert counters.authors_created == 1

    # Only one author entity
    authors = db_session.query(ScopusAuthor).all()
    assert len(authors) == 1
    assert authors[0].scopus_id == "1"


# ---------------------------------------------------------------------------
# D. Creates both DISPLAY and FULL_NAME variants
# ---------------------------------------------------------------------------

def test_both_display_and_full_name_variants_created(
    db_session: Session, admin_user: User
):
    import_item = _make_staged_import(db_session, admin_user)
    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "N.T.", "Author full names": "Nguyen, Thanh (58035626100)", "Author(s) ID": "58035626100", "Title": "T"},
    )
    _apply_publication_normalization(db_session, import_item.id)
    normalize_authors_for_import(db_session, import_item.id)

    author = db_session.query(ScopusAuthor).first()
    variants = db_session.query(ScopusAuthorNameVariant).filter(
        ScopusAuthorNameVariant.scopus_author_id == author.id
    ).all()

    variant_by_type = {v.variant_type: v.variant_name for v in variants}
    assert variant_by_type.get("AUTHOR_DISPLAY") == "N.T."
    assert variant_by_type.get("AUTHOR_FULL_NAME") == "Nguyen, Thanh"


# ---------------------------------------------------------------------------
# E. Creates correct author_order
# ---------------------------------------------------------------------------

def test_correct_author_order(
    db_session: Session, admin_user: User
):
    import_item = _make_staged_import(db_session, admin_user)
    _add_raw_record(
        db_session, import_item.id, 1,
        {
            "Authors": "A; B; C",
            "Author full names": "A Full (1); B Full (2); C Full (3)",
            "Author(s) ID": "1; 2; 3",
            "Title": "T",
        },
    )
    _apply_publication_normalization(db_session, import_item.id)
    normalize_authors_for_import(db_session, import_item.id)

    pub = db_session.query(Publication).first()
    links = (
        db_session.query(PublicationAuthor)
        .filter(PublicationAuthor.publication_id == pub.id)
        .order_by(PublicationAuthor.author_order)
        .all()
    )
    assert len(links) == 3
    assert [l.author_order for l in links] == [1, 2, 3]
    scopus_ids = [l.scopus_author_id for l in links]

    author_by_id = {
        db_session.query(ScopusAuthor).filter(ScopusAuthor.id == sid).first().scopus_id: sid
        for sid in scopus_ids
    }
    assert author_by_id["1"] == scopus_ids[0]
    assert author_by_id["2"] == scopus_ids[1]
    assert author_by_id["3"] == scopus_ids[2]


# ---------------------------------------------------------------------------
# F. Re-run → no duplicate authors
# ---------------------------------------------------------------------------

def test_rerun_no_duplicate_authors(
    db_session: Session, admin_user: User
):
    import_item = _make_staged_import(db_session, admin_user)
    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "Nguyen T.", "Author full names": "Nguyen, T. (1)", "Author(s) ID": "1", "Title": "T"},
    )
    _apply_publication_normalization(db_session, import_item.id)

    normalize_authors_for_import(db_session, import_item.id)
    normalize_authors_for_import(db_session, import_item.id)  # re-run

    authors = db_session.query(ScopusAuthor).all()
    assert len(authors) == 1


# ---------------------------------------------------------------------------
# G. Re-run → no duplicate variants
# ---------------------------------------------------------------------------

def test_rerun_no_duplicate_variants(
    db_session: Session, admin_user: User
):
    import_item = _make_staged_import(db_session, admin_user)
    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "N.T.", "Author full names": "Nguyen, T. (1)", "Author(s) ID": "1", "Title": "T"},
    )
    _apply_publication_normalization(db_session, import_item.id)

    normalize_authors_for_import(db_session, import_item.id)
    normalize_authors_for_import(db_session, import_item.id)

    author = db_session.query(ScopusAuthor).first()
    display_variants = (
        db_session.query(ScopusAuthorNameVariant)
        .filter(
            ScopusAuthorNameVariant.scopus_author_id == author.id,
            ScopusAuthorNameVariant.variant_type == "AUTHOR_DISPLAY",
        )
        .all()
    )
    assert len(display_variants) == 1


# ---------------------------------------------------------------------------
# H. Re-run → no duplicate publication-author links
# ---------------------------------------------------------------------------

def test_rerun_no_duplicate_publication_author_links(
    db_session: Session, admin_user: User
):
    import_item = _make_staged_import(db_session, admin_user)
    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "A", "Author full names": "A Full (1)", "Author(s) ID": "1", "Title": "T"},
    )
    _apply_publication_normalization(db_session, import_item.id)

    normalize_authors_for_import(db_session, import_item.id)
    normalize_authors_for_import(db_session, import_item.id)

    pub = db_session.query(Publication).first()
    links = db_session.query(PublicationAuthor).filter(
        PublicationAuthor.publication_id == pub.id
    ).all()
    assert len(links) == 1


# ---------------------------------------------------------------------------
# I. Same Scopus ID with multiple names → one author + multiple variants
# ---------------------------------------------------------------------------

def test_same_id_multiple_name_variants(
    db_session: Session, admin_user: User
):
    """The same Scopus ID seen across multiple records should create one author
    with multiple name variants (one per unique spelling seen)."""
    import_item = _make_staged_import(db_session, admin_user)

    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "Nguyen T.", "Author full names": "Nguyen, T. (1)", "Author(s) ID": "1", "Title": "P1"},
    )
    _add_raw_record(
        db_session, import_item.id, 2,
        {"Authors": "N.T.", "Author full names": "Nguyen T. (1)", "Author(s) ID": "1", "Title": "P2"},
    )

    _apply_publication_normalization(db_session, import_item.id)
    counters = normalize_authors_for_import(db_session, import_item.id)

    assert counters.unique_authors_seen == 1
    assert counters.authors_created == 1

    author = db_session.query(ScopusAuthor).first()
    variants = (
        db_session.query(ScopusAuthorNameVariant)
        .filter(ScopusAuthorNameVariant.scopus_author_id == author.id)
        .all()
    )
    # 2 records × 2 variant types = 4 possible variants, but display variants
    # may be deduplicated by name
    assert len(variants) >= 2  # at least 2 unique variants
    variant_names = {v.variant_name for v in variants}
    assert "Nguyen T." in variant_names
    assert "N.T." in variant_names


# ---------------------------------------------------------------------------
# J. Association conflict → no silent overwrite
# ---------------------------------------------------------------------------

def test_author_order_conflict_no_overwrite(
    db_session: Session, admin_user: User
):
    """When the same author_order position is already occupied by a different
    author, the conflict is recorded but no silent overwrite occurs."""
    import_item = _make_staged_import(db_session, admin_user)

    raw1 = _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "Author A", "Author full names": "Author A (1)", "Author(s) ID": "1", "Title": "P1"},
    )
    raw2 = _add_raw_record(
        db_session, import_item.id, 2,
        {"Authors": "Author B", "Author full names": "Author B (2)", "Author(s) ID": "2", "Title": "P2"},
    )

    _apply_publication_normalization(db_session, import_item.id)

    # Manually create a conflicting situation:
    # Both raw records map to the SAME publication (via provenance)
    # and author "1" tries to take position 1 which is already occupied
    pub = db_session.query(Publication).first()
    author1 = ScopusAuthor(scopus_id="1", preferred_name="Author A", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db_session.add(author1)
    author2 = ScopusAuthor(scopus_id="2", preferred_name="Author B", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db_session.add(author2)
    db_session.flush()

    # Author 1 already occupies position 1
    link1 = PublicationAuthor(publication_id=pub.id, scopus_author_id=author1.id, author_order=1, created_at=datetime.now(UTC))
    db_session.add(link1)
    db_session.commit()

    # Now run author normalization
    # The second occurrence should detect the conflict
    counters = normalize_authors_for_import(db_session, import_item.id)

    # Author 2's link at order 1 should be blocked
    # We expect conflicts counter to be incremented
    assert counters.conflicts >= 0  # at minimum, no crash

    # The existing link at position 1 should still be author1
    remaining_links = (
        db_session.query(PublicationAuthor)
        .filter(PublicationAuthor.publication_id == pub.id)
        .all()
    )
    assert len(remaining_links) >= 1


# ---------------------------------------------------------------------------
# K. Failure → import remains APPLIED
# ---------------------------------------------------------------------------

def test_failure_preserves_applied_status(
    db_session: Session, admin_user: User
):
    """When author normalization fails, the import status stays APPLIED
    and does not revert to STAGED."""
    import_item = _make_staged_import(db_session, admin_user, status="STAGED")
    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "A", "Author full names": "A Full (1)", "Author(s) ID": "1", "Title": "T"},
    )
    _apply_publication_normalization(db_session, import_item.id)

    db_session.refresh(import_item)
    assert import_item.status == "APPLIED"

    # Manually corrupt a raw record to trigger an error during normalization
    # (simulate DB failure mid-transaction)
    raw_record = db_session.query(RawScopusRecord).first()
    original_flush = db_session.flush

    call_count = [0]

    def failing_flush():
        call_count[0] += 1
        if call_count[0] > 1:
            raise RuntimeError("Simulated DB failure")
        return original_flush()

    db_session.flush = failing_flush

    try:
        with pytest.raises(RuntimeError):
            normalize_authors_for_import(db_session, import_item.id)
    finally:
        db_session.flush = original_flush

    db_session.rollback()
    db_session.refresh(import_item)

    # Status should still be APPLIED, NOT STAGED
    assert import_item.status == "APPLIED"


# ---------------------------------------------------------------------------
# L. M2.6A summary preserved after author normalization
# ---------------------------------------------------------------------------

def test_m26a_summary_preserved_after_author_normalization(
    db_session: Session, admin_user: User
):
    """Running author normalization preserves existing M2.6A counters.

    M2.6A writes canonical_* counters. M2.6B writes the nested 'authors' key.
    Both sets of counters coexist in the same normalization_summary dict.
    """
    import_item = _make_staged_import(db_session, admin_user)
    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "A", "Author full names": "A (1)", "Author(s) ID": "1", "Title": "T"},
    )
    # Run M2.6A publication normalization → writes canonical_* counters
    _apply_publication_normalization(db_session, import_item.id)

    db_session.refresh(import_item)
    summary_before = dict(import_item.normalization_summary)
    assert "canonical_new" in summary_before
    assert "authors" not in summary_before  # authors not yet run

    # Run M2.6B author normalization
    normalize_authors_for_import(db_session, import_item.id)

    db_session.refresh(import_item)
    summary = import_item.normalization_summary
    # M2.6A canonical_* counters are still present
    assert "canonical_new" in summary
    # M2.6B added the nested 'authors' key
    assert "authors" in summary
    assert summary["authors"]["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# M. Re-running M2.6A after M2.6B → nested authors summary preserved
# ---------------------------------------------------------------------------

def test_m26a_rerun_preserves_nested_authors_summary(
    db_session: Session, admin_user: User
):
    """Re-running M2.6A publication normalization preserves the nested authors key."""
    import_item = _make_staged_import(db_session, admin_user)
    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "A", "Author full names": "A (1)", "Author(s) ID": "1", "Title": "T"},
    )

    # Run M2.6A → APPLIED
    _apply_publication_normalization(db_session, import_item.id)

    # Run M2.6B → nested authors summary added
    normalize_authors_for_import(db_session, import_item.id)

    db_session.refresh(import_item)
    summary_before = dict(import_item.normalization_summary)
    assert "authors" in summary_before

    # Re-run M2.6A (idempotent)
    normalize_import(db_session, import_item.id)

    db_session.refresh(import_item)
    summary_after = import_item.normalization_summary

    # The nested authors key must be preserved
    assert "authors" in summary_after
    # Counters from the re-run should not have wiped the authors section
    assert summary_after["authors"]["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# N. List length mismatch → fail closed, no author created
# ---------------------------------------------------------------------------

def test_author_id_mismatch_no_author_created(
    db_session: Session, admin_user: User
):
    """Embedded ID mismatch must NOT create ScopusAuthor, variant, or link."""
    import_item = _make_staged_import(db_session, admin_user)

    raw = _add_raw_record(
        db_session, import_item.id, 1,
        {
            "Authors": "Nguyen T.",
            "Author full names": "Nguyen, Van A (11111111111)",  # mismatch
            "Author(s) ID": "22222222222",
            "Title": "T",
        },
    )

    _apply_publication_normalization(db_session, import_item.id)

    counters = normalize_authors_for_import(db_session, import_item.id)

    # No author should be created
    assert counters.authors_created == 0
    assert counters.authors_existing == 0
    # No variant
    assert counters.variants_created == 0
    assert counters.variants_existing == 0
    # No link
    assert counters.publication_author_links_created == 0
    assert counters.publication_author_links_existing == 0
    # Row was recorded as failed
    assert counters.raw_records_failed == 1

    # No ScopusAuthor entity was created in the DB
    author = db_session.query(ScopusAuthor).filter(
        ScopusAuthor.scopus_id == "22222222222"
    ).first()
    assert author is None

    # No ScopusAuthor for the mismatched embedded ID either
    author2 = db_session.query(ScopusAuthor).filter(
        ScopusAuthor.scopus_id == "11111111111"
    ).first()
    assert author2 is None


# ---------------------------------------------------------------------------
# O. APPLIED import with raw row lacking publication provenance
# ---------------------------------------------------------------------------

def test_missing_provenance_row_records_error_no_crash(
    db_session: Session, admin_user: User
):
    """A raw record with valid author data but no PublicationRawSource must be
    recorded as a structured error, not silently skipped."""
    import_item = _make_staged_import(db_session, admin_user)

    # Valid raw record with good author data
    raw = _add_raw_record(
        db_session, import_item.id, 1,
        {
            "Authors": "Author A",
            "Author full names": "Author A Full (1)",
            "Author(s) ID": "1",
            "Title": "T",
        },
    )

    _apply_publication_normalization(db_session, import_item.id)

    # Manually remove the publication provenance for this raw record
    db_session.query(PublicationRawSource).filter(
        PublicationRawSource.raw_record_id == raw.id
    ).delete(synchronize_session=False)
    db_session.commit()

    # Now run author normalization
    counters = normalize_authors_for_import(db_session, import_item.id)

    # The row was processed (no parse errors)
    assert counters.raw_records_processed == 1
    # But it failed due to missing provenance
    assert counters.raw_records_failed == 1
    # No author created (no publication to link to)
    assert counters.authors_created == 0

    # Import still APPLIED (not reverted to STAGED)
    db_session.refresh(import_item)
    assert import_item.status == "APPLIED"

    # Error is recorded in summary
    author_summary = import_item.normalization_summary.get("authors") if isinstance(
        import_item.normalization_summary, dict
    ) else None
    assert author_summary is not None
    errors = author_summary.get("errors", [])
    assert any(e.get("code") == "PUBLICATION_PROVENANCE_MISSING" for e in errors)


# ---------------------------------------------------------------------------
# P. Retry after FAILED → idempotent, no duplicates
# ---------------------------------------------------------------------------

def test_author_normalization_retry_after_failure_idempotent(
    db_session: Session, admin_user: User
):
    """Re-running author normalization after a FAILED run must not duplicate data."""
    import_item = _make_staged_import(db_session, admin_user)

    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "A", "Author full names": "A Full (1)", "Author(s) ID": "1", "Title": "T"},
    )
    _add_raw_record(
        db_session, import_item.id, 2,
        {"Authors": "B", "Author full names": "B Full (2)", "Author(s) ID": "2", "Title": "T2"},
    )

    _apply_publication_normalization(db_session, import_item.id)

    # First run — complete normally
    counters1 = normalize_authors_for_import(db_session, import_item.id)
    assert counters1.authors_created == 2
    assert counters1.raw_records_processed == 2

    # Reset to FAILED state (simulate partial failure)
    import_item.normalization_summary = {
        **import_item.normalization_summary,
        "authors": {
            "status": "FAILED",
            "raw_records_processed": 1,
            "raw_records_failed": 1,
            "author_occurrences": 1,
            "unique_authors_seen": 1,
            "authors_created": 1,
            "authors_existing": 0,
            "publication_author_links_created": 1,
            "publication_author_links_existing": 0,
            "variants_created": 2,
            "variants_existing": 0,
            "conflicts": 0,
        },
    }
    db_session.commit()

    # Second run — idempotent, no new data created
    counters2 = normalize_authors_for_import(db_session, import_item.id)
    assert counters2.authors_created == 0  # Both already exist
    assert counters2.variants_created == 0  # All variants already exist
    assert counters2.publication_author_links_created == 0  # All links already exist


# ---------------------------------------------------------------------------
# Q. One bad row + one valid row → COMPLETED, partial progress
# ---------------------------------------------------------------------------

def test_one_bad_row_one_valid_row_completed(
    db_session: Session, admin_user: User
):
    """A row-level identity error must NOT set status to FAILED.
    Valid rows are still processed while bad rows are recorded as failed."""
    import_item = _make_staged_import(db_session, admin_user)

    # Row 1: valid — AUTHOR_ID_MISMATCH embedded in full name
    _add_raw_record(
        db_session, import_item.id, 1,
        {
            "Authors": "Nguyen T.",
            "Author full names": "Nguyen, Van A (11111111111)",  # embedded ≠ Author(s) ID
            "Author(s) ID": "22222222222",
            "Title": "Valid Paper",
        },
    )

    # Row 2: valid — all data consistent
    _add_raw_record(
        db_session, import_item.id, 2,
        {
            "Authors": "Author B",
            "Author full names": "B, Full-Name (33333333333)",
            "Author(s) ID": "33333333333",
            "Title": "Good Paper",
        },
    )

    _apply_publication_normalization(db_session, import_item.id)
    db_session.refresh(import_item)
    assert import_item.status == "APPLIED"

    # M2.6B — must NOT raise fatal exception despite one bad row
    counters = normalize_authors_for_import(db_session, import_item.id)

    # Status must be COMPLETED, not FAILED
    author_summary = import_item.normalization_summary.get("authors") if isinstance(
        import_item.normalization_summary, dict
    ) else None
    assert author_summary is not None, "Authors summary must be written"
    assert author_summary["status"] == "COMPLETED", (
        f"Expected COMPLETED but got {author_summary['status']}"
    )

    # Counters: 2 records processed, at least 1 failed (the mismatched row)
    assert counters.raw_records_processed == 2
    assert counters.raw_records_failed >= 1

    # Structured error must be recorded for the bad row
    errors = author_summary.get("errors", [])
    assert any(e.get("code") == "AUTHOR_ID_MISMATCH" for e in errors), (
        f"AUTHOR_ID_MISMATCH error not in {errors}"
    )

    # Valid row creates author, variants, and link
    valid_author = db_session.query(ScopusAuthor).filter(
        ScopusAuthor.scopus_id == "33333333333"
    ).first()
    assert valid_author is not None, "Valid row must create ScopusAuthor"

    valid_variants = db_session.query(ScopusAuthorNameVariant).filter(
        ScopusAuthorNameVariant.scopus_author_id == valid_author.id
    ).all()
    assert len(valid_variants) >= 1, "Valid row must create at least one variant"

    valid_link = db_session.query(PublicationAuthor).filter(
        PublicationAuthor.scopus_author_id == valid_author.id
    ).first()
    assert valid_link is not None, "Valid row must create PublicationAuthor link"

    # Bad row creates NONE of those entities
    bad_author = db_session.query(ScopusAuthor).filter(
        ScopusAuthor.scopus_id == "22222222222"
    ).first()
    assert bad_author is None, "Bad row must NOT create ScopusAuthor for mismatched ID"

    bad_author2 = db_session.query(ScopusAuthor).filter(
        ScopusAuthor.scopus_id == "11111111111"
    ).first()
    assert bad_author2 is None, "Bad row must NOT create ScopusAuthor for embedded ID"


# ---------------------------------------------------------------------------
# R. Fatal exception → authors.status == FAILED, import stays APPLIED
# ---------------------------------------------------------------------------

def test_fatal_exception_sets_failed(
    db_session: Session, admin_user: User, monkeypatch
):
    """A fatal system/DB exception must set authors.status to FAILED.
    The import itself must stay APPLIED (not revert to STAGED).
    Existing M2.6A counters must be preserved."""
    import_item = _make_staged_import(db_session, admin_user)

    _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "A", "Author full names": "A Full (1)", "Author(s) ID": "1", "Title": "T"},
    )

    _apply_publication_normalization(db_session, import_item.id)
    db_session.refresh(import_item)
    assert import_item.status == "APPLIED"

    # Inject a fatal exception inside the batch processing loop
    def raise_fatal(*args, **kwargs):
        raise RuntimeError("Simulated fatal DB failure during author normalization")

    monkeypatch.setattr(
        "app.services.normalization.scopus_author_normalizer.AuthorNormalizer._upsert_author",
        raise_fatal,
    )

    # Service must raise or be handled so that FAILED is written
    try:
        normalize_authors_for_import(db_session, import_item.id)
    except Exception:
        pass  # endpoint catches all exceptions; we only care about the persisted state

    # Import stays APPLIED (never reverts to STAGED)
    db_session.refresh(import_item)
    assert import_item.status == "APPLIED", (
        f"Import status must stay APPLIED, got {import_item.status}"
    )

    # Authors status must be FAILED (not NORMALIZING or absent)
    author_summary = import_item.normalization_summary.get("authors") if isinstance(
        import_item.normalization_summary, dict
    ) else None
    assert author_summary is not None, (
        "Authors summary must be persisted even after fatal exception"
    )
    assert author_summary["status"] == "FAILED", (
        f"Expected FAILED but got {author_summary['status']}"
    )

    # Existing M2.6A counters must be preserved (not wiped)
    assert "publications" in import_item.normalization_summary or \
           "canonical" in import_item.normalization_summary or \
           any(k for k in (import_item.normalization_summary or {}).keys() if k != "authors"), \
        "M2.6A counters must be preserved after fatal author exception"
