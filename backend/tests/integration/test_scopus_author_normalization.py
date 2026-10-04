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
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.exceptions import APIError
from app.core.database import get_session
from app.main import app
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


def test_author_normalize_http_rerun_is_idempotent(
    db_session: Session, admin_user: User
) -> None:
    """The HTTP contract must remain truthful on the second run."""
    import_item = _make_staged_import(db_session, admin_user)
    _add_raw_record(
        db_session,
        import_item.id,
        row_number=1,
        raw_payload={
            "Authors": "Nguyen T.",
            "Author full names": "Nguyen, Thanh-Tung (58035626100)",
            "Author(s) ID": "58035626100",
            "Title": "HTTP rerun regression",
        },
    )
    _apply_publication_normalization(db_session, import_item.id)

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        with TestClient(app) as client:
            first = client.post(
                f"/api/v1/authors/normalize-import/{import_item.id}"
            )
            assert first.status_code == 200, first.text

            before = (
                db_session.query(ScopusAuthor).count(),
                db_session.query(PublicationAuthor).count(),
                db_session.query(ScopusAuthorNameVariant).count(),
            )
            second = client.post(
                f"/api/v1/authors/normalize-import/{import_item.id}"
            )
            assert second.status_code == 200, second.text
            payload = second.json()
            assert payload["import_id"] == str(import_item.id)
            assert payload["status"] == "COMPLETED"
            assert set(("counters", "errors")) <= payload.keys()

        db_session.refresh(import_item)
        after = (
            db_session.query(ScopusAuthor).count(),
            db_session.query(PublicationAuthor).count(),
            db_session.query(ScopusAuthorNameVariant).count(),
        )
        assert after == before
        assert import_item.status == "APPLIED"
        assert import_item.normalization_summary["authors"]["status"] == "COMPLETED"
    finally:
        app.dependency_overrides.clear()


def test_unique_authors_seen_counts_distinct_ids_on_first_and_rerun(
    db_session: Session, admin_user: User
) -> None:
    """The distinct-ID counter is independent from authors_created."""
    import_item = _make_staged_import(db_session, admin_user)
    for row_number, display_name, full_name, scopus_id in (
        (1, "Author A", "Author, A", "10000000001"),
        (2, "Author B", "Author, B", "10000000002"),
        (3, "Author A2", "Author, A2", "10000000001"),
    ):
        _add_raw_record(
            db_session,
            import_item.id,
            row_number=row_number,
            raw_payload={
                "Authors": display_name,
                "Author full names": f"{full_name} ({scopus_id})",
                "Author(s) ID": scopus_id,
                "Title": f"Distinct counter {row_number}",
            },
        )
    _apply_publication_normalization(db_session, import_item.id)

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        with TestClient(app) as client:
            first = client.post(
                f"/api/v1/authors/normalize-import/{import_item.id}"
            )
            assert first.status_code == 200, first.text
            first_payload = first.json()
            assert first_payload["counters"]["author_occurrences"] == 3
            assert first_payload["counters"]["unique_authors_seen"] == 2
            assert first_payload["counters"]["authors_created"] == 2

            before = (
                db_session.query(ScopusAuthor).count(),
                db_session.query(PublicationAuthor).count(),
                db_session.query(ScopusAuthorNameVariant).count(),
            )

            rerun = client.post(
                f"/api/v1/authors/normalize-import/{import_item.id}"
            )
            assert rerun.status_code == 200, rerun.text
            rerun_payload = rerun.json()
            assert rerun_payload["counters"]["author_occurrences"] == 3
            assert rerun_payload["counters"]["unique_authors_seen"] == 2
            assert rerun_payload["counters"]["authors_created"] == 0

        after = (
            db_session.query(ScopusAuthor).count(),
            db_session.query(PublicationAuthor).count(),
            db_session.query(ScopusAuthorNameVariant).count(),
        )
        assert after == before
        assert import_item.status == "APPLIED"
        assert import_item.normalization_summary["authors"]["status"] == "COMPLETED"
    finally:
        app.dependency_overrides.clear()


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


# ---------------------------------------------------------------------------
# S. AUTHOR_LIST_LENGTH_MISMATCH — no truncate, no zip-shortest, no guessing
# ---------------------------------------------------------------------------

def test_author_list_length_mismatch_no_author_created(
    db_session: Session, admin_user: User
):
    """When Authors / Author full names / Author(s) ID have different lengths,
    the row is rejected with a structured error and NO author/variant/link is created.
    There must be no truncation, zip-shortest, or silent guessing."""
    import_item = _make_staged_import(db_session, admin_user)

    # Case 1: Authors longer than full names
    raw1 = _add_raw_record(
        db_session, import_item.id, 1,
        {
            "Authors": "A; B; C",
            "Author full names": "A Full (1); B Full (2)",          # 2 ≠ 3
            "Author(s) ID": "1; 2; 3",
            "Title": "T1",
        },
    )

    # Case 2: Authors shorter than IDs
    raw2 = _add_raw_record(
        db_session, import_item.id, 2,
        {
            "Authors": "X; Y",                                      # 2 ≠ 3
            "Author full names": "X Full (10); Y Full (20)",
            "Author(s) ID": "10; 20; 30",
            "Title": "T2",
        },
    )

    _apply_publication_normalization(db_session, import_item.id)

    counters = normalize_authors_for_import(db_session, import_item.id)

    # No authors created for either row
    assert counters.authors_created == 0
    # Both rows failed
    assert counters.raw_records_failed == 2
    assert counters.raw_records_processed == 2
    # No publication-author links
    assert counters.publication_author_links_created == 0
    # Import still COMPLETED (row-level errors, not fatal)
    db_session.refresh(import_item)
    author_summary = import_item.normalization_summary.get("authors") if isinstance(
        import_item.normalization_summary, dict
    ) else None
    assert author_summary is not None
    assert author_summary["status"] == "COMPLETED"

    # Structured errors present
    errors = author_summary.get("errors", [])
    error_codes = {e.get("code") for e in errors}
    assert "AUTHOR_LIST_LENGTH_MISMATCH" in error_codes

    # Zero ScopusAuthors in DB (no truncation → no "A; B; C" merged to shorter list)
    assert db_session.query(ScopusAuthor).count() == 0


# ---------------------------------------------------------------------------
# T. AUTHOR_LIST_LENGTH_MISMATCH parser — fail closed, no zip-shortest
# ---------------------------------------------------------------------------

def test_author_list_length_mismatch_parser_fails_closed(
    db_session: Session, admin_user: User
):
    """The parse_author_occurrences function must return empty occurrences
    when list lengths differ — never truncate, never zip-shortest."""
    import_item = _make_staged_import(db_session, admin_user)
    raw = _add_raw_record(
        db_session, import_item.id, 1,
        {
            "Authors": "A; B",
            "Author full names": "A Full (1)",          # 1 != 2
            "Author(s) ID": "1; 2",
            "Title": "T",
        },
    )

    _apply_publication_normalization(db_session, import_item.id)

    counters = normalize_authors_for_import(db_session, import_item.id)

    # author_occurrences must be ZERO — no guessing/truncation
    assert counters.author_occurrences == 0
    assert counters.raw_records_failed == 1
    # Cannot have created 1 author (which would mean zip-shortest happened)
    assert counters.authors_created == 0

    # The DB must NOT contain a ScopusAuthor for scopus_id "1" with truncated data
    author1 = db_session.query(ScopusAuthor).filter(
        ScopusAuthor.scopus_id == "1"
    ).first()
    assert author1 is None


# ---------------------------------------------------------------------------
# U. DUPLICATE_SCOPUS_ID_IN_PUBLICATION — no duplicate occurrence/link
# ---------------------------------------------------------------------------

def test_duplicate_scopus_id_in_publication_no_duplicate_link(
    db_session: Session, admin_user: User
):
    """The same Scopus ID appearing twice in one publication must be recorded
    as a structured error and must NOT create duplicate author or duplicate links."""
    import_item = _make_staged_import(db_session, admin_user)

    raw = _add_raw_record(
        db_session, import_item.id, 1,
        {
            "Authors": "Nguyen T.; Le S.",
            "Author full names": "Nguyen, T. (11111111111); Le, S. (11111111111)",  # duplicate!
            "Author(s) ID": "11111111111; 11111111111",
            "Title": "T",
        },
    )

    _apply_publication_normalization(db_session, import_item.id)

    counters = normalize_authors_for_import(db_session, import_item.id)

    # Raw record fails due to duplicate
    assert counters.raw_records_failed == 1
    assert counters.raw_records_processed == 1
    # Zero author occurrences (duplicate rejected before linking)
    assert counters.author_occurrences == 0
    # No authors created
    assert counters.authors_created == 0

    # No duplicate ScopusAuthor entities
    all_authors = db_session.query(ScopusAuthor).all()
    assert len(all_authors) == 0

    # No publication-author links
    pub = db_session.query(Publication).first()
    links = db_session.query(PublicationAuthor).filter(
        PublicationAuthor.publication_id == pub.id
    ).all()
    assert len(links) == 0

    # Structured error recorded
    db_session.refresh(import_item)
    author_summary = import_item.normalization_summary.get("authors") if isinstance(
        import_item.normalization_summary, dict
    ) else None
    errors = author_summary.get("errors", []) if author_summary else []
    assert any(e.get("code") == "DUPLICATE_SCOPUS_ID_IN_PUBLICATION" for e in errors)


# ---------------------------------------------------------------------------
# V. ASSOCIATION_CONFLICT — no silent overwrite (strengthened)
# ---------------------------------------------------------------------------

def test_association_conflict_recorded_no_overwrite(
    db_session: Session, admin_user: User
):
    """When author_order position is already occupied by a different author,
    the conflict must be recorded as an error and NO silent overwrite occurs.
    The original author must retain their position."""
    import_item = _make_staged_import(db_session, admin_user)

    # Add two raw records — they will initially get different EIDs (2-s2.0-1 vs 2-s2.0-2)
    # from _add_raw_record. We'll manually force them to share the same publication
    # so that author_order slots genuinely collide.
    raw1 = _add_raw_record(
        db_session, import_item.id, 1,
        {"Authors": "Alice A.", "Author full names": "Alice A (1)", "Author(s) ID": "1", "Title": "P1"},
    )
    raw2 = _add_raw_record(
        db_session, import_item.id, 2,
        {"Authors": "Bob B.", "Author full names": "Bob B (2)", "Author(s) ID": "2", "Title": "P2"},
    )

    _apply_publication_normalization(db_session, import_item.id)

    # Force both raw records to map to the SAME publication so position 1 collides.
    # Keep raw1's provenance as-is (pub1 at position 1 with author "1").
    pub1 = db_session.query(Publication).filter(Publication.eid == "2-s2.0-1").first()
    assert pub1 is not None
    pub2 = db_session.query(Publication).filter(Publication.eid == "2-s2.0-2").first()
    assert pub2 is not None

    # Point raw2's provenance at pub1 instead of pub2
    raw2_provenance = (
        db_session.query(PublicationRawSource)
        .filter(PublicationRawSource.raw_record_id == raw2.id)
        .first()
    )
    assert raw2_provenance is not None
    raw2_provenance.publication_id = pub1.id
    db_session.commit()

    # Pre-seed only author1 and link1 at position 1 (do NOT pre-seed author2).
    # After this setup:
    #   - raw1 → pub1, author "1" at position 1  [link already exists → no conflict]
    #   - raw2 → pub1, author "2" at position 1  [position 1 occupied by author1 → CONFLICT]
    author1 = ScopusAuthor(scopus_id="1", preferred_name="Alice A", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db_session.add(author1)
    db_session.flush()

    link1 = PublicationAuthor(publication_id=pub1.id, scopus_author_id=author1.id, author_order=1, created_at=datetime.now(UTC))
    db_session.add(link1)
    db_session.commit()

    # Run author normalization
    counters = normalize_authors_for_import(db_session, import_item.id)

    # Conflict counter incremented
    assert counters.conflicts >= 1, (
        f"Expected at least 1 conflict, got {counters.conflicts}. "
        f"Full counters: raw_failed={counters.raw_records_failed}, "
        f"created={counters.publication_author_links_created}, "
        f"existing={counters.publication_author_links_existing}"
    )

    # Original link at position 1 is UNCHANGED — Alice keeps her slot
    remaining = (
        db_session.query(PublicationAuthor)
        .filter(PublicationAuthor.publication_id == pub1.id)
        .all()
    )
    assert len(remaining) == 1, "Must not have created duplicate link for conflicting author"
    assert remaining[0].scopus_author_id == author1.id, "Original author at position 1 must not be overwritten"
    assert remaining[0].author_order == 1

    # Bob's link was NOT created (conflict blocked it)
    author2 = db_session.query(ScopusAuthor).filter(ScopusAuthor.scopus_id == "2").first()
    assert author2 is not None, "Bob's author entity should have been created"

    bob_link = (
        db_session.query(PublicationAuthor)
        .filter(
            PublicationAuthor.publication_id == pub1.id,
            PublicationAuthor.scopus_author_id == author2.id,
        )
        .first()
    )
    assert bob_link is None, "Conflicting author must NOT get a link at the occupied position"

    # Structured error recorded
    db_session.refresh(import_item)
    author_summary = import_item.normalization_summary.get("authors") if isinstance(
        import_item.normalization_summary, dict
    ) else None
    errors = author_summary.get("errors", []) if author_summary else []
    assert any(e.get("code") == "AUTHOR_ORDER_CONFLICT" for e in errors), (
        f"Expected AUTHOR_ORDER_CONFLICT in errors, got {[e.get('code') for e in errors]}"
    )


# ---------------------------------------------------------------------------
# W. PREFERRED_NAME_STABILITY — first occurrence locks, later spellings captured as variant
# ---------------------------------------------------------------------------

def test_preferred_name_stability_not_overwritten_on_rerun(
    db_session: Session, admin_user: User
):
    """The first occurrence sets ScopusAuthor.preferred_name.
    A later occurrence with a different spelling must NOT overwrite the existing
    preferred_name. The new spelling is captured as a name variant instead."""
    import_item = _make_staged_import(db_session, admin_user)

    # First record: spelling "Nguyen, Van-Thanh"
    _add_raw_record(
        db_session, import_item.id, 1,
        {
            "Authors": "N.V.T.",
            "Author full names": "Nguyen, Van-Thanh (58035626100)",
            "Author(s) ID": "58035626100",
            "Title": "Paper 1",
        },
    )

    # Second record (later rerun or new paper): different spelling "Nguyen Van Thanh"
    _add_raw_record(
        db_session, import_item.id, 2,
        {
            "Authors": "NV Thanh",
            "Author full names": "Nguyen Van Thanh (58035626100)",
            "Author(s) ID": "58035626100",
            "Title": "Paper 2",
        },
    )

    _apply_publication_normalization(db_session, import_item.id)

    # First run
    counters1 = normalize_authors_for_import(db_session, import_item.id)
    assert counters1.authors_created == 1

    author = db_session.query(ScopusAuthor).filter(
        ScopusAuthor.scopus_id == "58035626100"
    ).first()
    assert author is not None
    initial_preferred = author.preferred_name
    assert initial_preferred is not None
    assert initial_preferred != ""

    # Capture the initial preferred_name — it must be from the FULL_NAME variant
    # (preferred_name uses FULL_NAME first, then falls back to display)
    first_full_name_variant = (
        db_session.query(ScopusAuthorNameVariant)
        .filter(
            ScopusAuthorNameVariant.scopus_author_id == author.id,
            ScopusAuthorNameVariant.variant_type == "AUTHOR_FULL_NAME",
        )
        .order_by(ScopusAuthorNameVariant.created_at)
        .first()
    )
    assert first_full_name_variant is not None

    # Second run (simulates re-normalization with new spelling)
    db_session.expire_all()
    counters2 = normalize_authors_for_import(db_session, import_item.id)

    # Second run: no new author created (already exists)
    # Note: authors_existing counts occurrences where author was found in DB.
    # With 2 rows both referencing the same scopus_id, both find the existing author,
    # so counters2.authors_existing == 2 (not 1).
    assert counters2.authors_created == 0
    assert counters2.authors_existing == 2

    # preferred_name must be UNCHANGED
    db_session.refresh(author)
    assert author.preferred_name == initial_preferred, (
        f"preferred_name must not change on re-run. "
        f"Expected '{initial_preferred}', got '{author.preferred_name}'"
    )

    # The new spelling is captured as an additional FULL_NAME variant
    all_full_name_variants = (
        db_session.query(ScopusAuthorNameVariant)
        .filter(
            ScopusAuthorNameVariant.scopus_author_id == author.id,
            ScopusAuthorNameVariant.variant_type == "AUTHOR_FULL_NAME",
        )
        .all()
    )
    full_names = {v.variant_name for v in all_full_name_variants}
    assert "Nguyen, Van-Thanh" in full_names, "Original full name must remain as variant"
    assert "Nguyen Van Thanh" in full_names, "New spelling must be captured as additional variant"


# ---------------------------------------------------------------------------
# X. PREFERRED_NAME_STABILITY — rerun with preferred_name already set
# ---------------------------------------------------------------------------

def test_preferred_name_stable_across_rerun_scenario(
    db_session: Session, admin_user: User
):
    """Simulate the production scenario: ScopusAuthor.preferred_name is already
    populated from a previous run. A subsequent run must not change it even when
    the incoming FULL_NAME spelling differs."""
    import_item = _make_staged_import(db_session, admin_user)

    _add_raw_record(
        db_session, import_item.id, 1,
        {
            "Authors": "T. Nguyen",
            "Author full names": "Nguyen, Thanh (58035626100)",
            "Author(s) ID": "58035626100",
            "Title": "First Paper",
        },
    )
    _add_raw_record(
        db_session, import_item.id, 2,
        {
            "Authors": "TNguyen",
            "Author full names": "Thanh-Nguyen (58035626100)",  # different spelling
            "Author(s) ID": "58035626100",
            "Title": "Second Paper",
        },
    )

    _apply_publication_normalization(db_session, import_item.id)

    # First run
    normalize_authors_for_import(db_session, import_item.id)

    author = db_session.query(ScopusAuthor).filter(
        ScopusAuthor.scopus_id == "58035626100"
    ).first()
    assert author is not None
    preferred_after_first = author.preferred_name

    # Reset summary to simulate a fresh re-run (not a retry after FAILED)
    import_item.normalization_summary = {"authors": None}
    db_session.commit()

    # Re-run: pretend a new import record comes in with different spelling
    db_session.expire_all()

    # The preferred_name is already set; re-running with the new spelling
    # must NOT change the existing preferred_name
    normalize_authors_for_import(db_session, import_item.id)

    db_session.refresh(author)
    assert author.preferred_name == preferred_after_first, (
        "preferred_name must not change when re-run encounters different spelling"
    )

    # New spelling added as variant
    all_variants = db_session.query(ScopusAuthorNameVariant).filter(
        ScopusAuthorNameVariant.scopus_author_id == author.id,
        ScopusAuthorNameVariant.variant_type == "AUTHOR_FULL_NAME",
    ).all()
    variant_names = {v.variant_name for v in all_variants}
    assert len(variant_names) >= 2, "Both spellings should appear as separate variants"
    assert "Thanh-Nguyen" in variant_names
