"""Integration tests for Scopus publication normalization — M2.6A.

Requires a real PostgreSQL database. These tests verify the full normalization
pipeline end-to-end: raw records → canonical publications → provenance links.

Tests cover:
1. Empty canonical DB + valid import → all NEW
2. All-existing import → all EXISTING_UNCHANGED
3. Mixed new/existing
4. Intra-file EID duplicates
5. Metadata change detection (no overwrite)
6. Invalid EID rows → NORMALIZATION_ERROR (not blocked, counted)
7. Provenance links correct
8. Idempotent re-normalization
9. Concurrent same-new-EID (real DB concurrency)
10. Concurrent same raw source
11. Failed/Cancelled/Processing imports cannot normalize
12. DELETE import safety after normalization (IMPORT_IN_USE)
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.models.publication import Publication, PublicationRawSource
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.models.governance import User, AuditEvent
from app.services.normalization.scopus_normalizer import (
    normalize_batch,
    normalize_import,
    normalize_single_raw,
    NormalizationCounters,
    ProvenanceConflict,
    link_provenance,
    normalize_eid,
)
from app.services.scopus_import_service import (
    cancel_import,
    delete_scopus_import,
    is_import_eligible_for_normalization,
    normalize_existing_import,
)
import app.services.normalization.scopus_normalizer as normalizer_module


# ---------------------------------------------------------------------------
# Database fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh isolated PostgreSQL schema per test.

    Never create/drop application tables in ``public``: doing so destroys a
    developer's acceptance dataset and leaves Alembic's version marker stale.
    """
    url = settings.database_url
    schema = f"test_m26a_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, pool_pre_ping=True, future=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
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
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="testadmin@example.test",
        password_hash="fakehash",
        display_name="Test Admin",
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


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def make_import(
    db: Session,
    status: str = "STAGED",
    total: int = 1,
    valid: int = 1,
    invalid: int = 0,
) -> ScopusImport:
    item = ScopusImport(
        id=uuid.uuid4(),
        file_name="test.csv",
        file_sha256="a" * 64,
        total_records=total,
        valid_records=valid,
        invalid_records=invalid,
        status=status,
        error_summary=None,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(item)
    db.commit()
    return item


def make_raw(
    db: Session,
    import_id: uuid.UUID,
    row_number: int,
    eid: str | None,
    payload: dict | None = None,
    validation_status: str = "VALID",
) -> RawScopusRecord:
    row = RawScopusRecord(
        id=uuid.uuid4(),
        import_id=import_id,
        row_number=row_number,
        row_hash="a" * 64,
        eid_raw=eid,
        doi_raw=None,
        raw_payload=payload or {"Title": f"Paper {row_number}"},
        validation_status=validation_status,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    return row


def count_publications(db: Session) -> int:
    return db.query(Publication).count()


def count_provenance(db: Session) -> int:
    return db.query(PublicationRawSource).count()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestNormalizationNewRecords:
    def test_all_new_records(self, db_session: Session) -> None:
        """All 5 VALID raw rows create 5 canonical publications."""
        import_ = make_import(db_session, total=5, valid=5)

        for i in range(1, 6):
            make_raw(
                db_session,
                import_id=import_.id,
                row_number=i,
                eid=f"2-s2.0-00000000{i}",
                payload={"Title": f"Paper {i}"},
            )

        counters = normalize_import(db_session, import_.id)

        assert counters.canonical_new == 5
        assert counters.canonical_existing == 0
        assert counters.canonical_failed == 0
        assert counters.canonical_processed == 5
        assert counters.invariant_holds()
        assert count_publications(db_session) == 5
        assert count_provenance(db_session) == 5

    def test_invalid_eid_not_counted_as_failed_pub(self, db_session: Session) -> None:
        """Raw row with no EID → NORMALIZATION_ERROR, no publication created."""
        import_ = make_import(db_session, total=2, valid=2)

        # Row with valid EID
        make_raw(db_session, import_.id, 1, "2-s2.0-000000001", {"Title": "Good paper"})
        # Row with no EID
        make_raw(db_session, import_.id, 2, None, {"Title": "No EID paper"}, validation_status="VALID")

        counters = normalize_import(db_session, import_.id)

        assert counters.canonical_new == 1
        assert counters.canonical_failed == 1
        assert count_publications(db_session) == 1
        assert count_provenance(db_session) == 1  # only the valid one

    def test_invalid_validation_status_filtered(self, db_session: Session) -> None:
        """INVALID raw rows are not processed during normalization."""
        import_ = make_import(db_session, total=2, valid=1, invalid=1)

        make_raw(
            db_session,
            import_.id,
            1,
            "2-s2.0-000000001",
            {"Title": "Valid paper"},
            validation_status="VALID",
        )
        make_raw(
            db_session,
            import_.id,
            2,
            "2-s2.0-000000002",
            {"Title": "Invalid paper"},
            validation_status="INVALID",
        )

        counters = normalize_import(db_session, import_.id)

        assert counters.canonical_processed == 1  # only VALID rows
        assert count_publications(db_session) == 1


class TestNormalizationExistingRecords:
    def test_existing_eid_reused(self, db_session: Session) -> None:
        """Same EID appearing again → publication reused, provenance added."""
        import_1 = make_import(db_session, total=1, valid=1)
        import_2 = make_import(db_session, total=1, valid=1)

        eid = "2-s2.0-000000001"
        make_raw(db_session, import_1.id, 1, eid, {"Title": "Paper A"})

        # First import: create
        counters1 = normalize_import(db_session, import_1.id)
        assert counters1.canonical_new == 1

        pub_id = db_session.query(Publication).filter(Publication.eid == eid).first().id

        # Second import: reuse
        make_raw(db_session, import_2.id, 1, eid, {"Title": "Paper A"})
        counters2 = normalize_import(db_session, import_2.id)

        assert counters2.canonical_new == 0
        assert counters2.canonical_existing == 1
        assert count_publications(db_session) == 1
        assert db_session.query(Publication).filter(Publication.eid == eid).first().id == pub_id

    def test_metadata_changed_not_overwritten(self, db_session: Session) -> None:
        """Same EID with different metadata → EXISTING_METADATA_CHANGED, canonical unchanged."""
        import_1 = make_import(db_session, total=1, valid=1)
        import_2 = make_import(db_session, total=1, valid=1)

        eid = "2-s2.0-000000001"

        # First import
        make_raw(
            db_session,
            import_1.id,
            1,
            eid,
            {"Title": "Original Title", "Year": "2024", "DOI": "10.1000/v1"},
        )
        counters1 = normalize_import(db_session, import_1.id)
        assert counters1.canonical_new == 1

        # Second import with different title
        make_raw(
            db_session,
            import_2.id,
            1,
            eid,
            {"Title": "Revised Title", "Year": "2024", "DOI": "10.1000/v1"},
        )
        counters2 = normalize_import(db_session, import_2.id)
        assert counters2.canonical_metadata_changed == 1
        assert counters2.canonical_existing == 0

        # Canonical title must NOT change
        pub = db_session.query(Publication).filter(Publication.eid == eid).first()
        assert pub.title == "Original Title"

    def test_rerun_idempotent(self, db_session: Session) -> None:
        """Normalizing the same import twice produces stable EXISTING counters."""
        import_ = make_import(db_session, total=2, valid=2)

        make_raw(db_session, import_.id, 1, "2-s2.0-000000001", {"Title": "Paper 1"})
        make_raw(db_session, import_.id, 2, "2-s2.0-000000002", {"Title": "Paper 2"})

        counters1 = normalize_import(db_session, import_.id)
        pub_count_after_first = count_publications(db_session)

        # Re-run
        counters2 = normalize_import(db_session, import_.id)

        assert counters2.canonical_new == 0
        assert counters2.canonical_existing == 2
        assert count_publications(db_session) == pub_count_after_first
        assert count_provenance(db_session) == 2  # idempotent: no duplicate links


class TestNormalizationIntraFileDuplicate:
    def test_intra_file_duplicate_counted(self, db_session: Session) -> None:
        """Same EID appearing twice in same import → first NEW, second INTRA_DUPLICATE."""
        import_ = make_import(db_session, total=3, valid=3)

        make_raw(db_session, import_.id, 1, "2-s2.0-000000001", {"Title": "Paper A"})
        make_raw(db_session, import_.id, 2, "2-s2.0-000000001", {"Title": "Paper A duplicate"})
        make_raw(db_session, import_.id, 3, "2-s2.0-000000002", {"Title": "Paper B"})

        counters = normalize_import(db_session, import_.id)

        assert counters.canonical_new == 2
        assert counters.canonical_intra_duplicate == 1
        assert counters.canonical_processed == 3
        assert count_publications(db_session) == 2

    def test_intra_file_duplicate_across_batches(self, db_session: Session) -> None:
        """Import-scope tracking catches A/B/C/A when batch_size is two."""
        import_ = make_import(db_session, total=4, valid=4)
        eids = [
            "2-s2.0-CROSS-BATCH-A",
            "2-s2.0-CROSS-BATCH-B",
            "2-s2.0-CROSS-BATCH-C",
            "2-s2.0-CROSS-BATCH-A",
        ]
        for row_number, eid in enumerate(eids, 1):
            title = "Paper A" if eid.endswith("A") else f"Paper {eid[-1]}"
            make_raw(db_session, import_.id, row_number, eid, {"Title": title})

        counters = normalize_import(db_session, import_.id, cancel_check_interval=2)

        assert counters.canonical_new == 3
        assert counters.canonical_existing == 1
        assert counters.canonical_intra_duplicate == 1
        assert counters.canonical_processed == 4
        assert count_publications(db_session) == 3


class TestProvenanceLinks:
    def test_provenance_links_correct(self, db_session: Session) -> None:
        """All normalized rows are linked to their canonical publication."""
        import_ = make_import(db_session, total=3, valid=3)

        eids = ["2-s2.0-000000001", "2-s2.0-000000002", "2-s2.0-000000003"]
        raw_ids = []
        for i, eid in enumerate(eids, 1):
            row = make_raw(db_session, import_.id, i, eid, {"Title": f"Paper {i}"})
            raw_ids.append(row.id)

        counters = normalize_import(db_session, import_.id)

        for raw_id in raw_ids:
            link = (
                db_session.query(PublicationRawSource)
                .filter(PublicationRawSource.raw_record_id == raw_id)
                .first()
            )
            assert link is not None, f"Missing provenance link for raw {raw_id}"

    def test_unique_raw_record_constraint(self, db_session: Session) -> None:
        """Each raw record links to exactly one publication."""
        import_ = make_import(db_session, total=1, valid=1)
        raw = make_raw(db_session, import_.id, 1, "2-s2.0-000000001", {"Title": "Paper"})
        existing_by_eid: dict = {}
        normalize_single_raw(db_session, raw, existing_by_eid)

        # Try to link same raw again
        pub = db_session.query(Publication).first()
        result = link_provenance(db_session, pub, raw)
        assert result is True  # idempotent


class TestImportEligibility:
    def test_staged_eligible(self, db_session: Session) -> None:
        item = make_import(db_session, status="STAGED")
        assert is_import_eligible_for_normalization(item) is True

    def test_failed_not_eligible(self, db_session: Session) -> None:
        item = make_import(db_session, status="FAILED")
        assert is_import_eligible_for_normalization(item) is False

    def test_cancelled_not_eligible(self, db_session: Session) -> None:
        item = make_import(db_session, status="CANCELLED")
        assert is_import_eligible_for_normalization(item) is False

    def test_processing_not_eligible(self, db_session: Session) -> None:
        item = make_import(db_session, status="PARSING")
        assert is_import_eligible_for_normalization(item) is False

    def test_normalize_existing_import_rejects_ineligible(
        self, db_session: Session, admin_user: User
    ) -> None:
        item = make_import(db_session, status="FAILED")
        from app.core.exceptions import APIError

        with pytest.raises(APIError) as exc_info:
            normalize_existing_import(db_session, item.id, actor=admin_user)
        assert exc_info.value.code == "IMPORT_NOT_ELIGIBLE_FOR_NORMALIZATION"


class TestCounterInvariants:
    def test_counters_sum_to_processed(self, db_session: Session) -> None:
        """canonical_processed == sum of four mutually-exclusive outcomes."""
        import_ = make_import(db_session, total=4, valid=4)

        make_raw(db_session, import_.id, 1, "2-s2.0-000000001", {"Title": "New paper"})
        # EID already exists from previous import
        import_2 = make_import(db_session, total=3, valid=3)
        make_raw(db_session, import_2.id, 1, "2-s2.0-000000001", {"Title": "Same paper"})
        make_raw(db_session, import_2.id, 2, "2-s2.0-000000002", {"Title": "New paper 2"})
        make_raw(db_session, import_2.id, 3, None, {"Title": "No EID paper"})

        counters = normalize_import(db_session, import_2.id)

        assert counters.canonical_processed == (
            counters.canonical_new
            + counters.canonical_existing
            + counters.canonical_metadata_changed
            + counters.canonical_failed
        )
        assert counters.invariant_holds()


class TestDeleteImportSafety:
    def test_normalized_import_blocks_delete(
        self, db_session: Session, admin_user: User
    ) -> None:
        """Deleting a normalized import must be blocked by IMPORT_IN_USE."""
        import_ = make_import(db_session, total=2, valid=2)

        make_raw(db_session, import_.id, 1, "2-s2.0-000000001", {"Title": "Paper 1"})
        make_raw(db_session, import_.id, 2, "2-s2.0-000000002", {"Title": "Paper 2"})

        normalize_import(db_session, import_.id)

        # Check downstream dependency
        in_use = (
            db_session.query(PublicationRawSource)
            .join(RawScopusRecord, PublicationRawSource.raw_record_id == RawScopusRecord.id)
            .filter(RawScopusRecord.import_id == import_.id)
            .first()
        )
        assert in_use is not None

        from app.core.exceptions import APIError

        with pytest.raises(APIError) as exc_info:
            delete_scopus_import(db_session, import_.id, admin_user)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "IMPORT_IN_USE"
        assert db_session.query(Publication).count() == 2


class TestConcurrentNormalization:
    def test_concurrent_same_new_eid_two_sessions(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both PostgreSQL transactions observe absence, then race the INSERT."""
        url = settings.database_url
        from sqlalchemy.pool import NullPool

        schema = db_session.info["test_schema"]
        engine = create_engine(
            url,
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        import_a = make_import(db_session, total=1, valid=1)
        import_b = make_import(db_session, total=1, valid=1)
        eid = "2-s2.0-TRUE-RACE-001"
        raw_a = make_raw(db_session, import_a.id, 1, eid, {"Title": "Race paper"})
        raw_b = make_raw(db_session, import_b.id, 1, eid, {"Title": "Race paper"})
        raw_ids = [raw_a.id, raw_b.id]
        db_session.commit()

        barrier = threading.Barrier(2)
        observed_absent: list[bool] = []
        connection_ids: list[int] = []
        violations: list[tuple[str | None, str | None]] = []
        observation_lock = threading.Lock()
        original_classifier = normalizer_module.is_publication_eid_unique_violation

        def recording_classifier(exc):
            orig = exc.orig
            diag = getattr(orig, "diag", None)
            with observation_lock:
                violations.append(
                    (
                        getattr(orig, "pgcode", None),
                        getattr(diag, "constraint_name", None),
                    )
                )
            return original_classifier(exc)

        monkeypatch.setattr(
            normalizer_module,
            "is_publication_eid_unique_violation",
            recording_classifier,
        )

        def worker(raw_id: uuid.UUID) -> tuple[str, bool]:
            with factory() as session:
                raw = session.query(RawScopusRecord).filter_by(id=raw_id).one()
                absent = session.query(Publication).filter_by(eid=eid).first() is None
                backend_pid = session.execute(text("SELECT pg_backend_pid()")).scalar_one()
                with observation_lock:
                    observed_absent.append(absent)
                    connection_ids.append(backend_pid)
                barrier.wait(timeout=10)
                result = normalize_single_raw(session, raw, {})
                outer_usable = session.execute(text("SELECT 1")).scalar_one() == 1
                session.commit()
                return result.outcome, outer_usable

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(worker, raw_ids))
        engine.dispose()

        assert observed_absent == [True, True]
        assert len(set(connection_ids)) == 2
        assert sorted(outcome for outcome, _ in results) == ["EXISTING_UNCHANGED", "NEW"]
        assert all(outer_usable for _, outer_usable in results)
        assert violations == [("23505", "uq_publications_eid")]
        db_session.expire_all()
        assert db_session.query(Publication).count() == 1
        links = db_session.query(PublicationRawSource).filter(
            PublicationRawSource.raw_record_id.in_(raw_ids)
        ).all()
        assert len(links) == 2
        assert len({link.publication_id for link in links}) == 1
        assert {import_a.status, import_b.status} == {"STAGED"}

    def test_concurrent_same_new_eid(self, db_session: Session) -> None:
        """Sequential same-session simulation of concurrent normalization.

        This test uses the same session to simulate what happens when two workers
        race: the first insert wins, the second encounters the unique constraint
        and recovers.  The same raw record normalized twice produces one NEW and
        one EXISTING_UNCHANGED outcome.
        """
        import_ = make_import(db_session, total=1, valid=1)
        raw = make_raw(db_session, import_.id, 1, "2-s2.0-SEQ-RACE-001", {"Title": "Race paper"})

        existing_by_eid: dict = {}
        result1 = normalize_single_raw(db_session, raw, existing_by_eid)
        assert result1.outcome == "NEW"

        # Second normalization with empty cache simulates losing the race
        existing_by_eid2: dict = {}
        result2 = normalize_single_raw(db_session, raw, existing_by_eid2)
        assert result2.outcome == "EXISTING_UNCHANGED"

        assert count_publications(db_session) == 1


class TestNormalizationCancellation:
    def test_cancel_between_batches_preserves_completed_work_and_raw_errors(
        self,
        db_session: Session,
        admin_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import_ = make_import(db_session, total=6, valid=6)
        raw_errors = {
            "duplicate_candidates": 1,
            "row_errors": [{"row_number": 99, "code": "RAW_WARNING"}],
        }
        import_.error_summary = raw_errors
        raw_ids: list[uuid.UUID] = []
        for row_number in range(1, 7):
            raw_ids.append(
                make_raw(
                    db_session,
                    import_.id,
                    row_number,
                    f"2-s2.0-CANCEL-{row_number:03d}",
                    {"Title": f"Paper {row_number}"},
                ).id
            )
        db_session.commit()

        first_batch_committed = threading.Event()
        allow_worker_to_continue = threading.Event()
        original_finalize = normalizer_module.Normalizer.finalize

        def pausing_finalize(self, db, import_id, **kwargs):
            original_finalize(self, db, import_id, **kwargs)
            if (
                kwargs.get("status") == "NORMALIZING"
                and self.counters.canonical_processed == 2
                and not first_batch_committed.is_set()
            ):
                first_batch_committed.set()
                assert allow_worker_to_continue.wait(timeout=10)

        monkeypatch.setattr(normalizer_module.Normalizer, "finalize", pausing_finalize)

        schema = db_session.info["test_schema"]
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

        def run_normalization() -> NormalizationCounters:
            with factory() as session:
                return normalize_import(session, import_.id, cancel_check_interval=2)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_normalization)
            assert first_batch_committed.wait(timeout=10)
            with factory() as cancel_session:
                actor = cancel_session.query(User).filter(User.id == admin_user.id).one()
                response = cancel_import(cancel_session, import_.id, actor)
                assert response is not None
                assert response.status == "CANCELLED"
            allow_worker_to_continue.set()
            counters = future.result(timeout=10)

        engine.dispose()
        db_session.expire_all()
        refreshed = db_session.query(ScopusImport).filter_by(id=import_.id).one()
        assert refreshed.status == "CANCELLED"
        assert refreshed.error_summary == raw_errors
        assert refreshed.normalization_summary["status"] == "CANCELLED"
        assert refreshed.normalization_summary["progress_percent"] < 100
        assert counters.canonical_processed == 2
        assert db_session.query(Publication).count() == 2
        linked_raw_ids = {
            link.raw_record_id for link in db_session.query(PublicationRawSource).all()
        }
        assert len(linked_raw_ids) == 2
        assert len(set(raw_ids) - linked_raw_ids) == 4


class TestNormalizationWithExistingPublications:
    def test_mixed_new_and_existing(self, db_session: Session) -> None:
        """First import creates publications; second import mixes NEW and EXISTING."""
        import_1 = make_import(db_session, total=3, valid=3)
        import_2 = make_import(db_session, total=4, valid=4)

        eids = ["2-s2.0-000000001", "2-s2.0-000000002", "2-s2.0-000000003"]
        for i, eid in enumerate(eids, 1):
            make_raw(db_session, import_1.id, i, eid, {"Title": f"Paper {i}"})

        normalize_import(db_session, import_1.id)

        # Second import: 2 old EIDs + 1 new EID + 1 already-existing EID (duplicate)
        make_raw(db_session, import_2.id, 1, "2-s2.0-000000001", {"Title": "Paper 1 again"})
        make_raw(db_session, import_2.id, 2, "2-s2.0-000000002", {"Title": "Paper 2 again"})
        make_raw(db_session, import_2.id, 3, "2-s2.0-000000003", {"Title": "Paper 3 again"})
        make_raw(db_session, import_2.id, 4, "2-s2.0-000000004", {"Title": "Paper 4 NEW"})

        counters = normalize_import(db_session, import_2.id)

        # EID 4 is new → NEW.  EIDs 1-3 already exist but titles differ →
        # EXISTING_METADATA_CHANGED (canonical not overwritten, diff recorded).
        assert counters.canonical_new == 1
        assert counters.canonical_existing == 0
        assert counters.canonical_metadata_changed == 3
        assert count_publications(db_session) == 4
