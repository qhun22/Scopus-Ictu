"""G04: transaction control flow of author normalization, using no database.

The fake session below models only what G04 relies on: pending -> flushed ->
committed state, SAVEPOINT rollback, the four unique keys plus the CHECK and
FK constraints of the three tables, and rows committed by a concurrent writer.
These tests prove control flow, ordering and counter bookkeeping. They do NOT
prove PostgreSQL transaction safety; see
tests/integration/test_author_normalizer_transactions_pg.py for that.
"""

from __future__ import annotations

import contextlib
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.identity import LecturerScopusIdentity, MappingReview
from app.models.publication import (
    PublicationAuthor,
    PublicationRawSource,
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
    AuthorOccurrence,
    integrity_violation,
    normalize_authors_for_import,
)


def uid(number: int) -> uuid.UUID:
    return uuid.UUID(int=number)


IMPORT_ID = uid(900)
PUB_1, PUB_2, PUB_MISSING = uid(1), uid(2), uid(404)


def driver_error(sqlstate: str, constraint: str | None) -> IntegrityError:
    diag = SimpleNamespace(constraint_name=constraint)
    return IntegrityError("INSERT ...", {}, SimpleNamespace(pgcode=sqlstate, diag=diag))


# Constraint name, SQLSTATE and key, mirroring models/publication.py and the
# initial migration. Each key returns None when the constraint does not apply.
CONSTRAINTS = {
    ScopusAuthor: [("uq_scopus_authors_scopus_id", "23505", lambda r: r.scopus_id)],
    ScopusAuthorNameVariant: [(
        "uq_author_name_variants", "23505",
        lambda r: (r.scopus_author_id, r.variant_type, r.variant_name),
    )],
    PublicationAuthor: [
        ("uq_publication_authors_order", "23505", lambda r: (r.publication_id, r.author_order)),
        ("uq_publication_authors_author", "23505",
         lambda r: (r.publication_id, r.scopus_author_id)),
    ],
}


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conditions):
        for condition in conditions:
            name, value = condition.left.key, condition.right.value
            if isinstance(value, (list, tuple)):
                self.rows = [row for row in self.rows if getattr(row, name) in value]
            else:
                self.rows = [row for row in self.rows if getattr(row, name) == value]
        return self

    def order_by(self, *args):
        return self

    def populate_existing(self):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return next(iter(self.rows), None)


class TxSession:
    """In-memory session: committed rows, one open transaction, savepoints."""

    MODELS = (ScopusAuthor, ScopusAuthorNameVariant, PublicationAuthor,
              ScopusImport, RawScopusRecord, PublicationRawSource)

    def __init__(self, publications=(PUB_1, PUB_2)):
        self.publications = set(publications)
        self.committed = {model: [] for model in self.MODELS}
        self.txn: list[object] = []      # flushed, not committed
        self.pending: list[object] = []  # added, not flushed
        self.savepoints: list[tuple[int, int]] = []
        self.races: list[tuple[type, object, object]] = []
        self.log: list[str] = []
        self.item = ScopusImport(
            id=IMPORT_ID, status="APPLIED", total_records=1, normalization_summary={},
        )
        self.committed[ScopusImport].append(self.item)

    # -- visibility -------------------------------------------------------
    def visible(self, model):
        return self.committed[model] + [row for row in self.txn if type(row) is model]

    def query(self, model):
        assert model in self.MODELS, f"Unexpected model queried: {model}"
        return Query(self.visible(model))

    # -- concurrency ------------------------------------------------------
    def race(self, model, key, winner):
        """A concurrent writer commits ``winner`` just before our INSERT of key."""
        self.races.append((model, key, winner))

    # -- unit of work -----------------------------------------------------
    def add(self, obj):
        assert type(obj) in self.MODELS, f"Unexpected model added: {type(obj)}"
        self.log.append(f"add:{type(obj).__name__}")
        self.pending.append(obj)

    def flush(self):
        self.log.append(f"flush:{len(self.pending)}")
        while self.pending:
            obj = self.pending[0]
            self._check(obj)
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            self.txn.append(self.pending.pop(0))

    def _check(self, obj):
        model = type(obj)
        for race_model, key, winner in list(self.races):
            if race_model is model and any(fn(obj) == key for _, _, fn in CONSTRAINTS[model]):
                self.races.remove((race_model, key, winner))
                self.committed[model].append(winner)
        if model is PublicationAuthor:
            if obj.author_order is None or obj.author_order < 1:
                raise driver_error("23514", "ck_publication_authors_author_order")
            if obj.publication_id not in self.publications:
                raise driver_error("23503", "fk_publication_authors_publication_id_publications")
        for name, sqlstate, fn in CONSTRAINTS.get(model, []):
            if any(fn(row) == fn(obj) for row in self.visible(model)):
                raise driver_error(sqlstate, name)

    @contextlib.contextmanager
    def _savepoint(self):
        self.log.append("SAVEPOINT")
        self.savepoints.append((len(self.txn), len(self.pending)))
        try:
            yield
        except BaseException:
            txn_mark, pending_mark = self.savepoints.pop()
            del self.txn[txn_mark:]
            del self.pending[pending_mark:]
            self.log.append("ROLLBACK TO SAVEPOINT")
            raise
        self.flush()
        self.savepoints.pop()
        self.log.append("RELEASE SAVEPOINT")

    def begin_nested(self):
        self.log.append("begin_nested")
        self.flush()  # SQLAlchemy flushes unconditionally before SAVEPOINT.
        return self._savepoint()

    def commit(self):
        self.flush()
        self.log.append("COMMIT")
        for obj in self.txn:
            self.committed[type(obj)].append(obj)
        self.txn.clear()

    def rollback(self):
        self.log.append("ROLLBACK")
        self.txn.clear()
        self.pending.clear()
        self.savepoints.clear()

    def expire_all(self):
        pass


def occurrence(author: int = 100, order: int = 1, *, raw: int = 10) -> AuthorOccurrence:
    return AuthorOccurrence(
        scopus_id=str(58000000000 + author), display_name=f"Synthetic {author}",
        full_name=None, author_order=order, embedded_id_matches=True,
        row_number=raw, raw_record_id=uid(raw), import_id=IMPORT_ID,
    )


def committed_author(author: int) -> ScopusAuthor:
    return ScopusAuthor(id=uid(author), scopus_id=str(58000000000 + author),
                        preferred_name=f"Synthetic {author}")


# ---------------------------------------------------------------------------
# Constraint identification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("orig", "expected"), [
    (SimpleNamespace(pgcode="23505", diag=SimpleNamespace(constraint_name="uq_x")),
     ("23505", "uq_x")),
    (SimpleNamespace(sqlstate="23503", diag=SimpleNamespace(constraint_name="fk_x")),
     ("23503", "fk_x")),
    (SimpleNamespace(pgcode="23505", diag=None), ("23505", None)),
    (SimpleNamespace(pgcode="23505", args=("uq_scopus_authors_scopus_id",)), ("23505", None)),
])
def test_integrity_violation_reads_sqlstate_and_constraint_without_message_parsing(
    orig, expected,
):
    assert integrity_violation(IntegrityError("INSERT", {}, orig)) == expected


def test_recognized_constraint_names_match_the_migrations():
    # Static check of the migration source; P5 checks the live catalog.
    versions = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    initial = (versions / "e5b3cf21c1d12b64_0001_initial_schema.py").read_text(encoding="utf-8")
    names = [UQ_SCOPUS_AUTHOR_ID, UQ_AUTHOR_NAME_VARIANT, UQ_PUBLICATION_AUTHOR,
             UQ_PUBLICATION_AUTHOR_ORDER, "ck_publication_authors_author_order",
             "fk_publication_authors_publication_id_publications"]
    for name in names:
        assert f'op.f("{name}")' in initial, name
    for later in versions.glob("*.py"):
        if later.name.startswith("e5b3cf21c1d12b64"):
            continue
        source = later.read_text(encoding="utf-8")
        assert not any(name in source for name in names), later.name


def test_integrity_violation_without_driver_error():
    exc = IntegrityError("INSERT", {}, None)
    exc.orig = None
    assert integrity_violation(exc) == (None, None)


# ---------------------------------------------------------------------------
# Savepoint ordering and the pending-state boundary
# ---------------------------------------------------------------------------

def test_insert_flushes_pending_state_before_savepoint_and_adds_inside_it():
    db, normalizer = TxSession(), AuthorNormalizer()
    normalizer._upsert_author(db, occurrence())
    assert db.log == [
        "flush:0", "begin_nested", "flush:0", "SAVEPOINT",
        "add:ScopusAuthor", "flush:1", "flush:0", "RELEASE SAVEPOINT",
    ]
    assert "ROLLBACK" not in db.log


def test_pending_duplicate_is_flushed_outside_recovery_scope_and_fails_closed():
    # A pending row with a *recognized* constraint must still not be recovered:
    # its failure belongs to earlier state, not to the row being inserted.
    db, normalizer = TxSession(), AuthorNormalizer()
    db.committed[ScopusAuthor].append(committed_author(100))
    db.pending.append(ScopusAuthor(scopus_id=str(58000000100), preferred_name="dup"))
    with pytest.raises(IntegrityError) as raised:
        normalizer._ensure_variant(db, uid(100), "AUTHOR_DISPLAY", "Synthetic 100", uid(10))
    assert integrity_violation(raised.value) == ("23505", UQ_SCOPUS_AUTHOR_ID)
    assert "begin_nested" not in db.log and "ROLLBACK" not in db.log
    assert normalizer.counters.variants_existing == 0
    assert normalizer.counters.variants_created == 0


# ---------------------------------------------------------------------------
# Expected unique races: earlier writes survive, counters follow outcomes
# ---------------------------------------------------------------------------

def test_author_race_keeps_earlier_batch_writes_and_counts_winner_as_existing():
    db, normalizer = TxSession(), AuthorNormalizer()
    first = normalizer._upsert_author(db, occurrence(101))
    normalizer._ensure_publication_author_link(db, first.id, PUB_1, 1, occurrence(101))
    winner = committed_author(102)
    db.race(ScopusAuthor, winner.scopus_id, winner)

    result = normalizer._upsert_author(db, occurrence(102))

    assert result is winner
    assert first in db.txn and len(db.visible(PublicationAuthor)) == 1
    assert "ROLLBACK" not in db.log and "ROLLBACK TO SAVEPOINT" in db.log
    assert normalizer.counters.authors_created == 1
    assert normalizer.counters.authors_existing == 1
    assert normalizer.counters.publication_author_links_created == 1


def test_variant_race_counts_existing_only_after_exact_key_is_proven():
    db, normalizer = TxSession(), AuthorNormalizer()
    db.committed[ScopusAuthor].append(committed_author(100))
    normalizer._ensure_variant(db, uid(100), "AUTHOR_DISPLAY", "Earlier", uid(10))
    winner = ScopusAuthorNameVariant(
        id=uid(7), scopus_author_id=uid(100), variant_type="AUTHOR_FULL_NAME",
        variant_name="Synthetic 100", variant_name_normalized="synthetic 100",
    )
    db.race(ScopusAuthorNameVariant, (uid(100), "AUTHOR_FULL_NAME", "Synthetic 100"), winner)

    normalizer._ensure_variant(db, uid(100), "AUTHOR_FULL_NAME", "Synthetic 100", uid(10))

    assert [v.variant_name for v in db.txn] == ["Earlier"]
    assert normalizer.counters.variants_created == 1
    assert normalizer.counters.variants_existing == 1


def test_link_pair_race_reclassifies_through_g03_drift_without_overwrite():
    db, normalizer = TxSession(), AuthorNormalizer()
    winner = PublicationAuthor(id=uid(8), publication_id=PUB_1,
                               scopus_author_id=uid(100), author_order=2)
    db.race(PublicationAuthor, (PUB_1, uid(100)), winner)

    normalizer._ensure_publication_author_link(db, uid(100), PUB_1, 4, occurrence(order=4))

    assert db.visible(PublicationAuthor) == [winner] and winner.author_order == 2
    assert normalizer.counters.publication_author_links_created == 0
    assert normalizer.counters.publication_author_links_existing == 1
    assert normalizer.counters.conflicts == 1
    drift, = normalizer.position_discrepancies.values()
    assert (drift["existing_author_order"], drift["observed_author_order"]) == (2, 4)


def test_link_slot_race_records_author_order_conflict():
    db, normalizer = TxSession(), AuthorNormalizer()
    winner = PublicationAuthor(id=uid(8), publication_id=PUB_1,
                               scopus_author_id=uid(555), author_order=3)
    db.race(PublicationAuthor, (PUB_1, 3), winner)

    normalizer._ensure_publication_author_link(db, uid(100), PUB_1, 3, occurrence(order=3))

    assert db.visible(PublicationAuthor) == [winner]
    assert normalizer.counters.publication_author_links_created == 0
    assert normalizer.counters.publication_author_links_existing == 0
    assert normalizer.counters.conflicts == 1
    assert normalizer.errors.errors[0]["code"] == "AUTHOR_ORDER_CONFLICT"


# ---------------------------------------------------------------------------
# Unexpected or unproven violations fail closed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("publication_id", "order", "expected"), [
    (PUB_MISSING, 1, ("23503", "fk_publication_authors_publication_id_publications")),
    (PUB_1, 0, ("23514", "ck_publication_authors_author_order")),
])
def test_fk_and_check_violations_propagate_and_are_never_counted(
    publication_id, order, expected,
):
    db, normalizer = TxSession(), AuthorNormalizer()
    with pytest.raises(IntegrityError) as raised:
        normalizer._ensure_publication_author_link(
            db, uid(100), publication_id, order, occurrence(order=order),
        )
    assert integrity_violation(raised.value) == expected
    assert "ROLLBACK" not in db.log and db.visible(PublicationAuthor) == []
    assert normalizer.counters.publication_author_links_existing == 0
    assert normalizer.counters.publication_author_links_created == 0


def test_unrecognized_unique_constraint_propagates(monkeypatch):
    db, normalizer = TxSession(), AuthorNormalizer()
    monkeypatch.setitem(CONSTRAINTS, ScopusAuthor, [
        ("uq_some_future_constraint", "23505", lambda r: r.preferred_name),
    ])
    db.committed[ScopusAuthor].append(ScopusAuthor(id=uid(9), scopus_id="1",
                                                   preferred_name="Synthetic 100"))
    with pytest.raises(IntegrityError):
        normalizer._upsert_author(db, occurrence(100))
    assert normalizer.counters.authors_existing == 0


@pytest.mark.parametrize("helper", ["author", "variant", "link"])
def test_recognized_conflict_without_provable_row_raises(helper, monkeypatch):
    # The driver reports the expected constraint but the re-query finds nothing.
    db, normalizer = TxSession(), AuthorNormalizer()
    name = {"author": UQ_SCOPUS_AUTHOR_ID, "variant": UQ_AUTHOR_NAME_VARIANT,
            "link": UQ_PUBLICATION_AUTHOR}[helper]

    def phantom_flush():
        if db.pending and db.savepoints:
            raise driver_error("23505", name)
        TxSession.flush(db)

    monkeypatch.setattr(db, "flush", phantom_flush)
    with pytest.raises(IntegrityError):
        if helper == "author":
            normalizer._upsert_author(db, occurrence())
        elif helper == "variant":
            normalizer._ensure_variant(db, uid(100), "AUTHOR_DISPLAY", "X", uid(10))
        else:
            normalizer._ensure_publication_author_link(db, uid(100), PUB_1, 1, occurrence())
    counters = normalizer.counters
    assert (counters.authors_existing, counters.variants_existing,
            counters.publication_author_links_existing) == (0, 0, 0)
    assert "ROLLBACK" not in db.log


def test_order_constraint_is_recognized_only_for_links():
    db, normalizer = TxSession(), AuthorNormalizer()
    db.committed[ScopusAuthor].append(committed_author(100))

    def wrong_constraint_flush():
        if db.pending and db.savepoints:
            raise driver_error("23505", UQ_PUBLICATION_AUTHOR_ORDER)
        TxSession.flush(db)

    db.flush = wrong_constraint_flush
    with pytest.raises(IntegrityError):
        normalizer._ensure_variant(db, uid(100), "AUTHOR_DISPLAY", "X", uid(10))


# ---------------------------------------------------------------------------
# Batch owner: atomic failure, honest counters, G03 observations
# ---------------------------------------------------------------------------

def raw_record(raw: int, ids: list[int]) -> RawScopusRecord:
    sids = [str(58000000000 + author) for author in ids]
    return RawScopusRecord(
        id=uid(raw), import_id=IMPORT_ID, row_number=raw, validation_status="VALID",
        raw_payload={
            "Authors": ";".join(f"Synthetic {sid}" for sid in sids),
            "Author full names": ";".join(f"Synthetic {sid} ({sid})" for sid in sids),
            "Author(s) ID": ";".join(sids),
        },
    )


def batch_session(rows: list[tuple[RawScopusRecord, uuid.UUID]]) -> TxSession:
    db = TxSession()
    db.item.total_records = len(rows)
    for record, publication_id in rows:
        db.committed[RawScopusRecord].append(record)
        db.committed[PublicationRawSource].append(
            PublicationRawSource(publication_id=publication_id, raw_record_id=record.id),
        )
    return db


def authors_summary(db: TxSession) -> dict:
    return db.item.normalization_summary["authors"]


def test_failed_batch_rolls_back_whole_and_summary_reports_only_committed_batches():
    db = batch_session([
        (raw_record(10, [101, 102]), PUB_1),
        (raw_record(11, [103]), PUB_MISSING),  # FK violation on the link insert
    ])
    with pytest.raises(IntegrityError):
        normalize_authors_for_import(db, IMPORT_ID, cancel_check_interval=1)

    assert {a.scopus_id for a in db.committed[ScopusAuthor]} == {"58000000101", "58000000102"}
    assert len(db.committed[PublicationAuthor]) == 2 and db.txn == []
    summary = authors_summary(db)
    assert summary["status"] == "FAILED"
    assert summary["authors_created"] == 2
    assert summary["publication_author_links_created"] == 2
    assert summary["variants_created"] == 4
    assert summary["raw_records_processed"] == 1
    assert summary["unique_authors_seen"] == 2
    rolled_back, = (e for e in summary["errors"] if e["code"] == "AUTHOR_BATCH_ROLLED_BACK")
    assert (rolled_back["first_row_number"], rolled_back["last_row_number"]) == (11, 11)
    assert rolled_back["error_type"] == "IntegrityError"


def test_rolled_back_batch_does_not_report_g03_observations_as_recorded():
    db = batch_session([
        (raw_record(10, [101, 100]), PUB_1),  # drift: author 100 stored at 1
        (raw_record(11, [100, 103]), PUB_2),  # drift on PUB_2, then FK failure
        (raw_record(12, [104]), PUB_MISSING),
    ])
    db.committed[ScopusAuthor].append(committed_author(100))
    db.committed[PublicationAuthor] += [
        PublicationAuthor(id=uid(81), publication_id=PUB_1,
                          scopus_author_id=uid(100), author_order=1),
        PublicationAuthor(id=uid(82), publication_id=PUB_2,
                          scopus_author_id=uid(100), author_order=2),
    ]
    with pytest.raises(IntegrityError):
        normalize_authors_for_import(db, IMPORT_ID, cancel_check_interval=2)

    summary = authors_summary(db)
    assert summary["status"] == "FAILED"
    # Batch 1 (rows 10-11) committed both drift observations; batch 2 had none.
    assert sorted(d["publication_id"] for d in summary["position_discrepancies"]) == sorted(
        [str(PUB_1), str(PUB_2)]
    )


def test_g03_observation_of_failed_batch_is_discarded():
    db = batch_session([
        (raw_record(10, [101]), PUB_1),
        (raw_record(11, [101, 100]), PUB_2),  # drift on PUB_2 ...
        (raw_record(12, [104]), PUB_MISSING),  # ... in the same failing batch
    ])
    db.committed[ScopusAuthor].append(committed_author(100))
    db.committed[PublicationAuthor].append(PublicationAuthor(
        id=uid(82), publication_id=PUB_2, scopus_author_id=uid(100), author_order=1,
    ))
    with pytest.raises(IntegrityError):
        normalize_authors_for_import(db, IMPORT_ID, cancel_check_interval=1)
    # Batches: [10] committed, [11] committed with drift, [12] failed.
    assert len(authors_summary(db)["position_discrepancies"]) == 1

    db2 = batch_session([
        (raw_record(10, [101]), PUB_1),
        (raw_record(11, [101, 102]), PUB_1),
        (raw_record(12, [101, 100]), PUB_2),  # drift on PUB_2 ...
        (raw_record(13, [104]), PUB_MISSING),  # ... in the same failing batch
    ])
    db2.committed[ScopusAuthor].append(committed_author(100))
    db2.committed[PublicationAuthor].append(PublicationAuthor(
        id=uid(82), publication_id=PUB_2, scopus_author_id=uid(100), author_order=1,
    ))
    with pytest.raises(IntegrityError):
        normalize_authors_for_import(db2, IMPORT_ID, cancel_check_interval=2)
    # Batches: [10, 11] committed, [12, 13] failed — the drift seen in row 12
    # and the slot conflict of row 12 were not persisted, so neither is reported.
    summary = authors_summary(db2)
    assert "position_discrepancies" not in summary
    assert summary["conflicts"] == 0


def test_replay_is_idempotent_for_authors_variants_and_links():
    db = batch_session([(raw_record(10, [101, 102]), PUB_1), (raw_record(11, [101]), PUB_2)])
    first = normalize_authors_for_import(db, IMPORT_ID, cancel_check_interval=1)
    rows = {model: len(db.committed[model]) for model in
            (ScopusAuthor, ScopusAuthorNameVariant, PublicationAuthor)}
    second = normalize_authors_for_import(db, IMPORT_ID, cancel_check_interval=1)

    assert (first.authors_created, first.variants_created,
            first.publication_author_links_created) == (2, 4, 3)
    assert (second.authors_created, second.variants_created,
            second.publication_author_links_created) == (0, 0, 0)
    assert (second.authors_existing, second.variants_existing,
            second.publication_author_links_existing) == (3, 6, 3)
    assert rows == {model: len(db.committed[model]) for model in rows}
    assert authors_summary(db)["status"] == "COMPLETED"
    assert "ROLLBACK" not in db.log


def test_race_recovery_and_failed_batch_leave_reviewer_identity_untouched():
    identity = LecturerScopusIdentity(
        id=uid(700), lecturer_id=uid(701), scopus_author_id=uid(102),
        status="APPROVED", version=3,
    )
    review = MappingReview(
        id=uid(702), identity_id=identity.id, reviewer_user_id=uid(703),
        action="APPROVE", from_status="CANDIDATE", to_status="APPROVED",
        evidence_snapshot={"synthetic": True},
    )
    before = (dict(identity.__dict__), dict(review.__dict__))
    db = batch_session([(raw_record(10, [102]), PUB_1), (raw_record(11, [103]), PUB_MISSING)])
    winner = committed_author(102)
    db.race(ScopusAuthor, winner.scopus_id, winner)
    with pytest.raises(IntegrityError):
        normalize_authors_for_import(db, IMPORT_ID, cancel_check_interval=1)
    # TxSession rejects any identity/review model, so none was queried or added.
    assert (identity.__dict__, review.__dict__) == before
    assert identity.status == "APPROVED" and identity.version == 3
