"""G04: PostgreSQL transaction behavior of author normalization.

Requires TEST_DATABASE_URL pointing to an allowlisted disposable database; the
conftest guard (tests/db_safety_guard.py) re-verifies the target before every
test and before cleanup. Each test works in its own schema, which is dropped
afterwards. Nothing here may run against the application database.

Races are made deterministic in two ways:
- a hook commits the conflicting row from a second connection immediately
  before our INSERT, after our pre-check already missed it (P1, P6);
- a real two-connection race where our INSERT blocks on an uncommitted row
  until the other transaction commits (P2), with bounded waits.
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from sqlalchemy.orm import Session, sessionmaker

import app.services.normalization.scopus_author_normalizer as author_module
from app.models.base import Base
from app.models.publication import (
    Publication,
    PublicationAuthor,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.normalization.scopus_author_normalizer import (
    UQ_AUTHOR_NAME_VARIANT,
    UQ_PUBLICATION_AUTHOR,
    UQ_PUBLICATION_AUTHOR_ORDER,
    UQ_SCOPUS_AUTHOR_ID,
    AuthorNormalizer,
    integrity_violation,
    normalize_authors_for_import,
)
from app.services.normalization.scopus_normalizer import normalize_import
from tests.db_safety_guard import assert_safe_for_destructive_test

LOCK_WAIT_SECONDS = 15
THREAD_JOIN_SECONDS = 30


# ---------------------------------------------------------------------------
# Fixtures: one disposable schema per test inside the verified test database
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(isolated_db_engine: Engine | None) -> Generator[sessionmaker, None, None]:
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL test database available.")
    schema = f"g04_txn_{uuid.uuid4().hex}"
    with isolated_db_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        isolated_db_engine.url,
        pool_pre_ping=True,
        future=True,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=30000 "
                       f"-clock_timeout={LOCK_WAIT_SECONDS * 2}s"
        },
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    factory.schema = schema  # type: ignore[attr-defined]
    try:
        Base.metadata.create_all(bind=engine)
        yield factory
    finally:
        engine.dispose()
        assert_safe_for_destructive_test(isolated_db_engine)
        with isolated_db_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def _sid(n: int) -> str:
    return str(58000000000 + n)


def _payload(authors: list[int]) -> dict:
    sids = [_sid(n) for n in authors]
    return {
        "Authors": ";".join(f"Synthetic {sid}" for sid in sids),
        "Author full names": ";".join(f"Synthetic {sid} ({sid})" for sid in sids),
        "Author(s) ID": ";".join(sids),
        "Title": "G04 synthetic title " + "-".join(sids),
    }


def make_applied_import(
    factory: sessionmaker, rows: list[tuple[str, list[int]]],
) -> uuid.UUID:
    """Create a synthetic import with one raw record per (eid, authors) row,
    then run M2.6A so publications and provenance exist and it is APPLIED."""
    import_id = uuid.uuid4()
    with factory() as db:
        db.add(ScopusImport(
            id=import_id, file_name=f"g04_{import_id.hex}.csv",
            file_sha256=hashlib.sha256(import_id.bytes).hexdigest(),
            total_records=len(rows), valid_records=len(rows), invalid_records=0,
            status="STAGED", version=1,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        db.commit()
        for row_number, (eid, authors) in enumerate(rows, start=1):
            payload = _payload(authors)
            db.add(RawScopusRecord(
                id=uuid.uuid4(), import_id=import_id, row_number=row_number,
                row_hash=hashlib.sha256(f"{import_id}{row_number}".encode()).hexdigest(),
                eid_raw=eid, doi_raw=None, raw_payload=payload,
                validation_status="VALID", validation_errors=None,
                created_at=datetime.now(UTC),
            ))
        db.commit()
        normalize_import(db, import_id)
        assert db.get(ScopusImport, import_id).status == "APPLIED"
    return import_id


def counts(factory: sessionmaker) -> dict[str, int]:
    with factory() as db:
        return {
            "authors": db.query(ScopusAuthor).count(),
            "variants": db.query(ScopusAuthorNameVariant).count(),
            "links": db.query(PublicationAuthor).count(),
        }


def author_ids(factory: sessionmaker) -> set[str]:
    with factory() as db:
        return {a.scopus_id for a in db.query(ScopusAuthor).all()}


def authors_summary(factory: sessionmaker, import_id: uuid.UUID) -> dict:
    with factory() as db:
        return db.get(ScopusImport, import_id).normalization_summary["authors"]


def commit_from_other_connection(factory: sessionmaker, build: Callable[[Session], object]):
    with factory() as other:
        other.add(build(other))
        other.commit()


def hook_before_insert(monkeypatch, match: Callable[[object], bool], action: Callable[[], None]):
    """Run ``action`` once, right before the matching INSERT's savepoint."""
    real = author_module._insert_in_savepoint
    fired = []

    def hooked(db, obj, recoverable):
        if not fired and match(obj):
            fired.append(obj)
            action()
        return real(db, obj, recoverable)

    monkeypatch.setattr(author_module, "_insert_in_savepoint", hooked)
    return fired


# ---------------------------------------------------------------------------
# P5 — constraint names and SQLSTATEs as reported by the real driver
# ---------------------------------------------------------------------------

def test_p5_constraint_names_exist_in_postgresql(pg):
    with pg() as db:
        names = set(db.execute(text(
            "SELECT c.conname FROM pg_constraint c "
            "JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = :schema"
        ), {"schema": pg.schema}).scalars())
    assert {
        UQ_SCOPUS_AUTHOR_ID, UQ_AUTHOR_NAME_VARIANT, UQ_PUBLICATION_AUTHOR,
        UQ_PUBLICATION_AUTHOR_ORDER, "ck_publication_authors_author_order",
        "fk_publication_authors_publication_id_publications",
        "fk_publication_authors_scopus_author_id_scopus_authors",
    } <= names


def test_p5_driver_reports_sqlstate_and_constraint_for_each_violation(pg):
    import_id = make_applied_import(pg, [("2-s2.0-g04p5", [1, 2])])
    with pg() as db:
        normalize_authors_for_import(db, import_id)
    with pg() as db:
        pub = db.query(Publication).one()
        a1, a2 = (db.query(ScopusAuthor).filter(ScopusAuthor.scopus_id == _sid(n)).one()
                  for n in (1, 2))
        # Each case violates exactly one constraint.
        cases = [
            (ScopusAuthor(scopus_id=_sid(1), preferred_name="dup"),
             ("23505", UQ_SCOPUS_AUTHOR_ID)),
            (ScopusAuthorNameVariant(
                scopus_author_id=a1.id, variant_type="AUTHOR_DISPLAY",
                variant_name=f"Synthetic {_sid(1)}", variant_name_normalized="x"),
             ("23505", UQ_AUTHOR_NAME_VARIANT)),
            (PublicationAuthor(publication_id=pub.id, scopus_author_id=a1.id, author_order=9),
             ("23505", UQ_PUBLICATION_AUTHOR)),
            (PublicationAuthor(publication_id=uuid.uuid4(), scopus_author_id=a2.id,
                               author_order=1),
             ("23503", "fk_publication_authors_publication_id_publications")),
        ]
        for obj, expected in cases:
            with pytest.raises(IntegrityError) as raised, db.begin_nested():
                db.add(obj)
                db.flush()
            assert integrity_violation(raised.value) == expected
        # The outer transaction survived every savepoint rollback.
        assert db.query(ScopusAuthor).count() == 2
        db.rollback()

    with pg() as db:
        pub = db.query(Publication).one()
        lone = ScopusAuthor(scopus_id=_sid(3), preferred_name="lone")
        db.add(lone)
        db.flush()
        with pytest.raises(IntegrityError) as raised, db.begin_nested():
            db.add(PublicationAuthor(publication_id=pub.id, scopus_author_id=lone.id,
                                     author_order=0))
            db.flush()
        assert integrity_violation(raised.value) == (
            "23514", "ck_publication_authors_author_order")
        with pytest.raises(IntegrityError) as raised, db.begin_nested():
            db.add(PublicationAuthor(publication_id=pub.id, scopus_author_id=lone.id,
                                     author_order=1))
            db.flush()
        assert integrity_violation(raised.value) == ("23505", UQ_PUBLICATION_AUTHOR_ORDER)
        db.rollback()


# ---------------------------------------------------------------------------
# P1 — earlier valid writes survive an expected uniqueness conflict
# ---------------------------------------------------------------------------

def test_p1_author_race_keeps_earlier_batch_writes(pg, monkeypatch):
    import_id = make_applied_import(pg, [("2-s2.0-g04p1a", [1]), ("2-s2.0-g04p1b", [2])])
    fired = hook_before_insert(
        monkeypatch,
        lambda obj: isinstance(obj, ScopusAuthor) and obj.scopus_id == _sid(2),
        lambda: commit_from_other_connection(
            pg, lambda _: ScopusAuthor(scopus_id=_sid(2), preferred_name="winner")),
    )
    with pg() as db:
        result = normalize_authors_for_import(db, import_id)  # one batch: rows 1 and 2

    assert fired, "the race hook did not fire"
    assert author_ids(pg) == {_sid(1), _sid(2)}
    # Author 1 and its variants/link were flushed before the conflict and survive.
    assert counts(pg) == {"authors": 2, "variants": 4, "links": 2}
    assert (result.authors_created, result.authors_existing) == (1, 1)
    summary = authors_summary(pg, import_id)
    assert summary["status"] == "COMPLETED"
    assert summary["authors_created"] == 1 and summary["publication_author_links_created"] == 2


# ---------------------------------------------------------------------------
# P2 — two sessions race on the same Scopus author (real lock wait)
# ---------------------------------------------------------------------------

def _wait_for_lock_waiter(pg: sessionmaker, deadline: float) -> bool:
    with pg() as probe:
        while time.monotonic() < deadline:
            waiting = probe.execute(text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock' "
                "AND pid <> pg_backend_pid()"
            )).scalar_one()
            if waiting:
                return True
            probe.rollback()
            time.sleep(0.05)
    return False


def test_p2_concurrent_sessions_create_one_author_and_keep_prior_writes(pg):
    import_id = make_applied_import(pg, [("2-s2.0-g04p2a", [1]), ("2-s2.0-g04p2b", [2])])
    holder = pg()
    outcome: dict[str, object] = {}

    def run_normalization():
        try:
            with pg() as db:
                outcome["counters"] = normalize_authors_for_import(db, import_id)
        except BaseException as exc:  # reported to the main thread
            outcome["error"] = exc

    worker = threading.Thread(target=run_normalization, daemon=True)
    try:
        holder.add(ScopusAuthor(scopus_id=_sid(2), preferred_name="holder"))
        holder.flush()  # row lock held, not committed: invisible to the worker
        worker.start()
        assert _wait_for_lock_waiter(pg, time.monotonic() + LOCK_WAIT_SECONDS), (
            "worker never blocked on the uncommitted author row")
        holder.commit()
        worker.join(THREAD_JOIN_SECONDS)
        assert not worker.is_alive(), "worker did not finish in time"
    finally:
        holder.rollback()
        holder.close()
        worker.join(THREAD_JOIN_SECONDS)

    assert "error" not in outcome, outcome.get("error")
    counters = outcome["counters"]
    assert (counters.authors_created, counters.authors_existing) == (1, 1)
    with pg() as db:
        assert db.query(ScopusAuthor).filter(ScopusAuthor.scopus_id == _sid(2)).count() == 1
    assert counts(pg) == {"authors": 2, "variants": 4, "links": 2}
    assert authors_summary(pg, import_id)["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# P3/P4 — unexpected FK and CHECK violations roll back the whole batch
# ---------------------------------------------------------------------------

def test_p3_fk_violation_rolls_back_batch_and_reports_failed(pg, monkeypatch):
    import_id = make_applied_import(
        pg, [("2-s2.0-g04p3a", [1]), ("2-s2.0-g04p3b", [2, 3]), ("2-s2.0-g04p3c", [4])])
    with pg() as db:
        row2 = db.query(RawScopusRecord).filter(RawScopusRecord.row_number == 2).one().id
    real = AuthorNormalizer.record_occurrences

    def broken_provenance(self, occurrences, db, mapping):
        if occurrences and occurrences[0].raw_record_id == row2:
            mapping = {**mapping, row2: uuid.uuid4()}  # publication does not exist
        return real(self, occurrences, db, mapping)

    monkeypatch.setattr(AuthorNormalizer, "record_occurrences", broken_provenance)
    with pytest.raises(IntegrityError) as raised, pg() as db:
        normalize_authors_for_import(db, import_id, cancel_check_interval=1)

    assert integrity_violation(raised.value)[0] == "23503"
    # Batch 1 committed; batch 2 (author 2 was flushed before its link failed)
    # left nothing; batch 3 never ran.
    assert author_ids(pg) == {_sid(1)}
    assert counts(pg) == {"authors": 1, "variants": 2, "links": 1}
    summary = authors_summary(pg, import_id)
    assert summary["status"] == "FAILED"
    assert (summary["authors_created"], summary["variants_created"],
            summary["publication_author_links_created"],
            summary["publication_author_links_existing"]) == (1, 2, 1, 0)
    assert summary["raw_records_processed"] == 1
    assert any(e["code"] == "AUTHOR_BATCH_ROLLED_BACK" for e in summary["errors"])


def test_p4_check_violation_rolls_back_batch(pg, monkeypatch):
    import_id = make_applied_import(pg, [("2-s2.0-g04p4a", [1]), ("2-s2.0-g04p4b", [2])])
    real_parse = author_module.parse_author_occurrences

    def zero_position(raw_record):
        occurrences, errors = real_parse(raw_record)
        if raw_record.row_number == 2:
            for occ in occurrences:
                occ.author_order = 0
        return occurrences, errors

    monkeypatch.setattr(author_module, "parse_author_occurrences", zero_position)
    with pytest.raises(IntegrityError) as raised, pg() as db:
        normalize_authors_for_import(db, import_id, cancel_check_interval=1)
    assert integrity_violation(raised.value) == ("23514", "ck_publication_authors_author_order")
    assert author_ids(pg) == {_sid(1)}
    assert authors_summary(pg, import_id)["status"] == "FAILED"


# ---------------------------------------------------------------------------
# P6 — duplicate author-order and pair races (G03 compatible)
# ---------------------------------------------------------------------------

def test_p6_slot_race_records_conflict_without_overwrite(pg, monkeypatch):
    import_id = make_applied_import(pg, [("2-s2.0-g04p6", [1])])
    with pg() as db:
        pub_id = db.query(Publication).one().id
    commit_from_other_connection(
        pg, lambda _: ScopusAuthor(id=uuid.UUID(int=77), scopus_id=_sid(77),
                                   preferred_name="slot owner"))
    hook_before_insert(
        monkeypatch, lambda obj: isinstance(obj, PublicationAuthor),
        lambda: commit_from_other_connection(pg, lambda _: PublicationAuthor(
            publication_id=pub_id, scopus_author_id=uuid.UUID(int=77), author_order=1)),
    )
    with pg() as db:
        counters = normalize_authors_for_import(db, import_id)

    assert (counters.publication_author_links_created,
            counters.publication_author_links_existing, counters.conflicts) == (0, 0, 1)
    with pg() as db:
        link, = db.query(PublicationAuthor).all()
        assert (link.scopus_author_id, link.author_order) == (uuid.UUID(int=77), 1)
    summary = authors_summary(pg, import_id)
    assert summary["status"] == "COMPLETED"
    assert any(e["code"] == "AUTHOR_ORDER_CONFLICT" for e in summary["errors"])


def test_p6_pair_race_with_other_position_is_g03_drift(pg, monkeypatch):
    import_id = make_applied_import(pg, [("2-s2.0-g04p6b", [5, 1])])  # author 1 at position 2
    with pg() as db:
        pub_id = db.query(Publication).one().id

    def winner_link():
        with pg() as other:
            author = other.query(ScopusAuthor).filter(ScopusAuthor.scopus_id == _sid(1)).one()
            other.add(PublicationAuthor(publication_id=pub_id, scopus_author_id=author.id,
                                        author_order=7))
            other.commit()

    # Author 1 must already be committed for the other connection to link it.
    commit_from_other_connection(pg, lambda _: ScopusAuthor(scopus_id=_sid(1),
                                                            preferred_name="pre"))
    hook_before_insert(
        monkeypatch,
        lambda obj: isinstance(obj, PublicationAuthor) and obj.author_order == 2,
        winner_link,
    )
    with pg() as db:
        counters = normalize_authors_for_import(db, import_id)

    assert counters.publication_author_links_existing == 1
    summary = authors_summary(pg, import_id)
    drift, = summary["position_discrepancies"]  # G03 observation, committed
    assert (drift["existing_author_order"], drift["observed_author_order"]) == (7, 2)
    with pg() as db:
        stored = db.query(PublicationAuthor).filter(
            PublicationAuthor.author_order == 7).one()
        assert stored.publication_id == pub_id  # canonical position not overwritten


# ---------------------------------------------------------------------------
# P7 — pending state is flushed outside the recovery scope
# ---------------------------------------------------------------------------

def test_p7_pending_duplicate_fails_closed_before_savepoint(pg):
    import_id = make_applied_import(pg, [("2-s2.0-g04p7", [1])])
    with pg() as db:
        normalize_authors_for_import(db, import_id)
    with pg() as db:
        author = db.query(ScopusAuthor).one()
        db.add(ScopusAuthor(scopus_id=_sid(1), preferred_name="pending duplicate"))
        normalizer = AuthorNormalizer()
        with pytest.raises(IntegrityError) as raised:
            normalizer._ensure_variant(db, author.id, "AUTHOR_DISPLAY", "new", uuid.uuid4())
        assert integrity_violation(raised.value) == ("23505", UQ_SCOPUS_AUTHOR_ID)
        assert normalizer.counters.variants_existing == 0
        # Not recovered: the outer transaction must now be rolled back by its owner.
        with pytest.raises(PendingRollbackError):
            db.query(ScopusAuthor).count()
        db.rollback()


# ---------------------------------------------------------------------------
# P8 — replay is idempotent
# ---------------------------------------------------------------------------

def test_p8_replay_is_idempotent(pg):
    import_id = make_applied_import(pg, [("2-s2.0-g04p8a", [1, 2]), ("2-s2.0-g04p8b", [2])])
    with pg() as db:
        first = normalize_authors_for_import(db, import_id, cancel_check_interval=1)
    before = counts(pg)
    with pg() as db:
        second = normalize_authors_for_import(db, import_id, cancel_check_interval=1)
    assert counts(pg) == before == {"authors": 2, "variants": 4, "links": 3}
    assert (first.authors_created, second.authors_created, second.authors_existing) == (2, 0, 3)
    assert second.publication_author_links_existing == 3
    assert authors_summary(pg, import_id)["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# P9/P10 — G03 observations: kept when committed, dropped with a rolled-back batch
# ---------------------------------------------------------------------------

def test_p10_g03_observations_follow_transaction_outcome(pg, monkeypatch):
    # Import A fixes author 1 at position 1 on both publications.
    first = make_applied_import(pg, [("2-s2.0-g04d1", [1]), ("2-s2.0-g04d2", [1])])
    with pg() as db:
        normalize_authors_for_import(db, first)
    # Import B re-observes both publications with author 1 at position 2, then
    # row 3 fails. Batch size 2: rows 1-2 (both drifts) commit, row 3 fails.
    second = make_applied_import(
        pg, [("2-s2.0-g04d1", [9, 1]), ("2-s2.0-g04d2", [9, 1]), ("2-s2.0-g04d3", [3])])
    with pg() as db:
        row3 = db.query(RawScopusRecord).filter(
            RawScopusRecord.import_id == second, RawScopusRecord.row_number == 3).one().id
    real = AuthorNormalizer.record_occurrences

    def fail_row3(self, occurrences, db, mapping):
        if occurrences and occurrences[0].raw_record_id == row3:
            mapping = {**mapping, row3: uuid.uuid4()}
        return real(self, occurrences, db, mapping)

    monkeypatch.setattr(AuthorNormalizer, "record_occurrences", fail_row3)
    with pytest.raises(IntegrityError), pg() as db:
        normalize_authors_for_import(db, second, cancel_check_interval=2)
    summary = authors_summary(pg, second)
    assert summary["status"] == "FAILED"
    assert len(summary["position_discrepancies"]) == 2  # both from the committed batch

    # Import C: the drift row shares its batch with the failing row.
    third = make_applied_import(pg, [
        ("2-s2.0-g04d5", [3]), ("2-s2.0-g04d6", [4]),
        ("2-s2.0-g04d1", [9, 1]), ("2-s2.0-g04d7", [6]),
    ])
    with pg() as db:
        row4 = db.query(RawScopusRecord).filter(
            RawScopusRecord.import_id == third, RawScopusRecord.row_number == 4).one().id

    def fail_row4(self, occurrences, db, mapping):
        if occurrences and occurrences[0].raw_record_id == row4:
            mapping = {**mapping, row4: uuid.uuid4()}
        return real(self, occurrences, db, mapping)

    monkeypatch.setattr(AuthorNormalizer, "record_occurrences", fail_row4)
    with pytest.raises(IntegrityError), pg() as db:
        normalize_authors_for_import(db, third, cancel_check_interval=2)
    # Batch [1, 2] commits; batch [3, 4] rolls back, so the drift and slot
    # conflict observed in row 3 are not reported as recorded.
    summary = authors_summary(pg, third)
    assert summary["status"] == "FAILED"
    assert "position_discrepancies" not in summary
    assert summary["conflicts"] == 0
