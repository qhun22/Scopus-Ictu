"""G03: synthetic author-order replay through real services, using no database."""

from __future__ import annotations

import contextlib
import copy
import json
import uuid

import pytest

from app.models.identity import LecturerScopusIdentity, MappingReview
from app.models.publication import PublicationAuthor, ScopusAuthor, ScopusAuthorNameVariant
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.normalization.scopus_author_normalizer import (
    AuthorNormalizer,
    AuthorOccurrence,
    normalize_authors_for_import,
)
from app.services.normalization.scopus_normalizer import Normalizer


def uid(number: int) -> uuid.UUID:
    return uuid.UUID(int=number)


def occurrence(order: int | None = 4, *, raw: int = 10, author: int = 100) -> AuthorOccurrence:
    return AuthorOccurrence(
        scopus_id=str(58000000000 + author),
        display_name=f"Synthetic Author {author}",
        full_name=None,
        author_order=order,
        embedded_id_matches=True,
        row_number=raw,
        raw_record_id=uid(raw),
        import_id=uid(900),
    )


def link(order: int | None = 2, *, author: int = 100) -> PublicationAuthor:
    return PublicationAuthor(
        id=uid(1000 + author), publication_id=uid(1),
        scopus_author_id=uid(author), author_order=order,
    )


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conditions):
        for condition in conditions:
            name, value = condition.left.key, getattr(condition.right, "value", None)
            self.rows = [row for row in self.rows if getattr(row, name) == value]
        return self

    def first(self):
        return next(iter(self.rows), None)


class FakeSession:
    """Evaluate exact equality predicates; reject unknown ORM models and rollback."""

    def __init__(self, links=(), *, summary=None):
        self.links = list(links)
        self.item = ScopusImport(id=uid(900), normalization_summary=summary or {})
        self.rows = {
            PublicationAuthor: self.links,
            ScopusImport: [self.item],
            ScopusAuthor: [],
            ScopusAuthorNameVariant: [],
        }
        self.added = []
        self.commits = 0

    def query(self, model):
        assert model in self.rows, f"Unexpected model queried: {model}"
        return Query(list(self.rows[model]))

    def add(self, obj):
        assert type(obj) in self.rows, f"Unexpected model added: {type(obj)}"
        if obj.id is None:
            obj.id = uid(5000 + len(self.added))
        self.rows[type(obj)].append(obj)
        self.added.append(obj)

    def flush(self):
        # This fake only checks the association constraints relevant to G03.
        pairs, positions = set(), set()
        for item in self.links:
            # A seeded NULL link represents legacy/inconsistent input only.
            if item in self.added:
                assert item.author_order is not None and item.author_order >= 1
            pair = (item.publication_id, item.scopus_author_id)
            assert pair not in pairs
            pairs.add(pair)
            if item.author_order is not None:
                slot = (item.publication_id, item.author_order)
                assert slot not in positions
                positions.add(slot)

    def begin_nested(self):
        # G04 inserts run in a savepoint; no conflict is ever raised here.
        return contextlib.nullcontext()

    def commit(self):
        self.commits += 1  # In memory only; no SQLAlchemy Session/engine exists.

    def rollback(self):
        raise AssertionError("G03 must not enter integrity-recovery handling")


def ensure(normalizer, db, observed, *, author=100):
    normalizer._ensure_publication_author_link(
        db, uid(author), uid(1), observed.author_order, observed,
    )


def persisted(db):
    return db.item.normalization_summary["authors"].get("position_discrepancies", [])


def test_new_association_preserves_current_behavior():
    db, normalizer = FakeSession(), AuthorNormalizer()
    ensure(normalizer, db, occurrence(2))
    assert len(db.links) == 1
    assert db.links[0].author_order == 2
    assert normalizer.counters.publication_author_links_created == 1
    assert normalizer.counters.conflicts == 0


def test_same_position_is_idempotent():
    original = link()
    db, normalizer = FakeSession([original]), AuthorNormalizer()
    for _ in range(2):
        ensure(normalizer, db, occurrence(2))
    assert db.links == [original] and db.added == []
    assert normalizer.counters.publication_author_links_existing == 2
    assert normalizer.counters.conflicts == 0
    assert normalizer.errors.errors == []


@pytest.mark.parametrize(("stored", "observed"), [(2, 4), (4, 2), (7, 9), (9, 7)])
def test_known_position_drift_is_reported_without_overwrite(stored, observed):
    original = link(stored)
    db, normalizer = FakeSession([original]), AuthorNormalizer()
    ensure(normalizer, db, occurrence(observed))
    assert original.author_order == stored and db.added == []
    assert normalizer.counters.publication_author_links_existing == 1
    assert normalizer.counters.conflicts == 1
    error, = normalizer.errors.errors
    assert error["code"] == "AUTHOR_POSITION_DRIFT"
    assert error["existing_author_order"] == stored
    assert error["observed_author_order"] == observed
    assert error["raw_record_id"] == str(uid(10))
    assert error["import_id"] == str(uid(900))
    normalizer.finalize(db, uid(900))
    conflict, = persisted(db)
    assert conflict["publication_id"] == str(uid(1))
    assert conflict["publication_author_id"] == str(original.id)
    assert conflict["scopus_author_id"] == str(uid(100))
    assert conflict["scopus_id"] == occurrence().scopus_id
    assert conflict["existing_author_order"] == stored
    assert conflict["observed_author_order"] == observed
    assert conflict["observations"] == [{
        "raw_record_id": str(uid(10)), "import_id": str(uid(900)), "row_number": 10,
    }]


@pytest.mark.parametrize(("stored", "observed"), [(2, None), (None, None), (None, 4)])
def test_missing_position_is_not_a_conflict_or_silent_promotion(stored, observed):
    original = link(stored)
    db, normalizer = FakeSession([original]), AuthorNormalizer()
    ensure(normalizer, db, occurrence(observed))
    assert original.author_order == stored
    assert normalizer.counters.conflicts == 0 and normalizer.errors.errors == []
    normalizer.finalize(db, uid(900))
    assert persisted(db) == []


def test_new_association_without_position_is_not_inserted_or_called_a_conflict():
    db, normalizer = FakeSession(), AuthorNormalizer()
    ensure(normalizer, db, occurrence(None))
    assert db.links == [] and db.added == []
    assert normalizer.counters.conflicts == 0
    error, = normalizer.errors.errors
    assert error["code"] == "AUTHOR_ORDER_MISSING"
    assert error["raw_record_id"] == str(uid(10))


def test_multiple_authors_including_swapped_slots_and_late_author():
    originals = [link(2), link(4, author=200), link(7, author=300)]
    db, normalizer = FakeSession(originals), AuthorNormalizer()
    for author, order in [(100, 4), (200, 2), (300, 7), (400, 8)]:
        ensure(normalizer, db, occurrence(order, author=author), author=author)
    normalizer.finalize(db, uid(900))
    assert [item.author_order for item in originals] == [2, 4, 7]
    assert [item.author_order for item in db.links] == [2, 4, 7, 8]
    assert len(persisted(db)) == 2
    assert normalizer.counters.conflicts == 2
    assert normalizer.counters.publication_author_links_created == 1


def test_existing_different_author_slot_conflict_is_unchanged():
    db, normalizer = FakeSession([link(2, author=200)]), AuthorNormalizer()
    ensure(normalizer, db, occurrence(2))
    assert len(db.links) == 1 and db.added == []
    assert normalizer.counters.conflicts == 1
    assert normalizer.errors.errors[0]["code"] == "AUTHOR_ORDER_CONFLICT"


@pytest.mark.parametrize("orders", [(2, 4), (4, 2)])
def test_reversed_import_order_preserves_first_position_but_detects_drift(orders):
    db = FakeSession()
    first = AuthorNormalizer()
    ensure(first, db, occurrence(orders[0], raw=10))
    first.finalize(db, uid(900))
    earlier_summary = copy.deepcopy(db.item.normalization_summary)
    newer_import = ScopusImport(id=uid(901), normalization_summary={})
    db.rows[ScopusImport].append(newer_import)
    later = AuthorNormalizer()
    newer_observation = occurrence(orders[1], raw=11)
    newer_observation.import_id = uid(901)
    ensure(later, db, newer_observation)
    later.finalize(db, uid(901))
    assert db.links[0].author_order == orders[0]
    assert db.item.normalization_summary == earlier_summary
    conflict, = newer_import.normalization_summary["authors"]["position_discrepancies"]
    assert (conflict["existing_author_order"], conflict["observed_author_order"]) == orders
    assert conflict["observations"][0]["import_id"] == str(uid(901))


def test_repeated_mismatch_and_rerun_do_not_duplicate_persisted_conflicts():
    db = FakeSession([link()], summary={"canonical_new": 1, "other": {"keep": True}})
    for _ in range(2):
        normalizer = AuthorNormalizer()
        normalizer.finalize(db, uid(900), status="NORMALIZING")
        for _ in range(3):
            ensure(normalizer, db, occurrence(4))
        normalizer.finalize(db, uid(900), status="NORMALIZING")
        normalizer.finalize(db, uid(900))
        assert normalizer.counters.conflicts == 1
        assert len(normalizer.errors.errors) == 1
        assert len(persisted(db)) == 1
        assert len(persisted(db)[0]["observations"]) == 1
    assert db.item.normalization_summary["canonical_new"] == 1
    assert db.item.normalization_summary["other"] == {"keep": True}
    snapshot = copy.deepcopy(persisted(db))
    # Empty restart/checkpoint must not erase earlier evidence.
    AuthorNormalizer().finalize(db, uid(900), status="FAILED")
    assert persisted(db) == snapshot


def test_distinct_raw_observations_share_one_conflict_with_deterministic_provenance():
    results = []
    for raw_order in [(12, 10, 11, 10), (10, 11, 12, 11)]:
        db, normalizer = FakeSession([link()]), AuthorNormalizer()
        for raw in raw_order:
            ensure(normalizer, db, occurrence(4, raw=raw))
        normalizer.finalize(db, uid(900))
        assert normalizer.counters.conflicts == 1
        conflict, = persisted(db)
        assert len(conflict["observations"]) == 3
        results.append(json.dumps(persisted(db), sort_keys=True))
    assert results[0] == results[1]


def test_provenance_merges_across_normalizer_instances_without_duplicate_conflicts():
    db = FakeSession([link()])
    for raw in [12, 10, 12]:
        normalizer = AuthorNormalizer()
        normalizer.finalize(db, uid(900), status="NORMALIZING")
        ensure(normalizer, db, occurrence(4, raw=raw))
        normalizer.finalize(db, uid(900))
    conflict, = persisted(db)
    assert [item["row_number"] for item in conflict["observations"]] == [10, 12]


def test_drift_provenance_is_not_lost_to_fifty_error_sample_cap():
    db, normalizer = FakeSession(), AuthorNormalizer()
    for offset in range(60):
        author = 100 + offset
        # Separate publications avoid unrelated slot-uniqueness conflicts.
        original = link(2, author=author)
        original.publication_id = uid(2000 + offset)
        db.links.append(original)
        observed = occurrence(4, raw=10 + offset, author=author)
        normalizer._ensure_publication_author_link(
            db, uid(author), original.publication_id, 4, observed,
        )
    normalizer.finalize(db, uid(900))
    assert normalizer.counters.conflicts == 60
    assert len(db.item.normalization_summary["authors"]["errors"]) == 50
    assert len(persisted(db)) == 60
    json.dumps(db.item.normalization_summary)  # All UUID provenance is JSON-safe.


def test_multiple_observed_positions_and_author_iteration_are_deterministic():
    results = []
    observations = [(100, 4), (100, 5), (200, 3)]
    for sequence in [observations, list(reversed(observations))]:
        db, normalizer = FakeSession([link(2), link(6, author=200)]), AuthorNormalizer()
        for author, order in sequence:
            ensure(normalizer, db, occurrence(order, author=author), author=author)
        normalizer.finalize(db, uid(900))
        assert normalizer.counters.conflicts == 3
        assert len(persisted(db)) == 3
        results.append(json.dumps(persisted(db), sort_keys=True))
    assert results[0] == results[1]


def test_publication_renormalization_preserves_position_diagnostic():
    db, normalizer = FakeSession([link()]), AuthorNormalizer()
    ensure(normalizer, db, occurrence(4))
    normalizer.finalize(db, uid(900))
    previous = copy.deepcopy(db.item.normalization_summary["authors"])
    Normalizer().finalize(db, uid(900), status="COMPLETED")
    assert db.item.normalization_summary["authors"] == previous


def test_record_occurrences_preserves_approved_identity_and_review():
    identity = LecturerScopusIdentity(
        id=uid(700), lecturer_id=uid(701), scopus_author_id=uid(100),
        status="APPROVED", version=3,
    )
    review = MappingReview(
        id=uid(702), identity_id=identity.id, reviewer_user_id=uid(703),
        action="APPROVE", from_status="CANDIDATE", to_status="APPROVED",
        evidence_snapshot={"synthetic": True},
    )
    protected_before = (dict(identity.__dict__), dict(review.__dict__))
    db, normalizer = FakeSession([link()]), AuthorNormalizer()
    db.rows[ScopusAuthor].append(ScopusAuthor(id=uid(100), scopus_id=occurrence().scopus_id))
    normalizer.record_occurrences([occurrence(4)], db, {uid(10): uid(1)})
    normalizer.finalize(db, uid(900))
    assert normalizer.counters.conflicts == 1
    assert (identity.__dict__, review.__dict__) == protected_before
    assert identity.status == "APPROVED" and identity.version == 3
    assert db.links[0].author_order == 2


@pytest.mark.parametrize("observed_position", [4, 8])
def test_entry_point_checkpoints_retain_drift_and_same_import_replay(
    monkeypatch, observed_position,
):
    # Exercise actual parser -> record_occurrences -> link check -> finalize.
    # Only query/loading plumbing is faked; no public API or SQL is invoked.
    from app.models.publication import PublicationRawSource

    class BatchQuery(Query):
        def filter(self, *conditions):
            return self  # One eligible synthetic import/raw/provenance only.

        def order_by(self, *args):
            return self

        def all(self):
            return self.rows

        def populate_existing(self):
            return self

    class BatchSession(FakeSession):
        def query(self, model):
            if model in (RawScopusRecord, PublicationRawSource, ScopusImport):
                return BatchQuery(list(self.rows[model]))
            return super().query(model)

        def expire_all(self):
            pass

    db = BatchSession([link()])
    db.item.status, db.item.total_records = "APPLIED", 1
    ids = [58000000000 + 200 + i for i in range(1, observed_position)]
    ids.append(58000000100)
    raw = RawScopusRecord(
        id=uid(10), import_id=uid(900), row_number=10, validation_status="VALID",
        raw_payload={
            "Authors": ";".join(f"Synthetic {sid}" for sid in ids),
            "Author full names": ";".join(f"Synthetic {sid} ({sid})" for sid in ids),
            "Author(s) ID": ";".join(map(str, ids)),
        },
    )
    db.rows[RawScopusRecord] = [raw]
    db.rows[PublicationRawSource] = [PublicationRawSource(
        publication_id=uid(1), raw_record_id=raw.id,
    )]
    db.rows[ScopusAuthor].append(ScopusAuthor(id=uid(100), scopus_id=occurrence().scopus_id))
    # Suppress variants only, to keep this test focused on position processing.
    monkeypatch.setattr(AuthorNormalizer, "_ensure_variant", lambda *args: None)
    for _ in range(2):
        counters = normalize_authors_for_import(db, uid(900), cancel_check_interval=1)
        assert counters.conflicts >= 1  # Slot 2 also has an unrelated author collision.
        conflict, = persisted(db)
        assert conflict["observed_author_order"] == observed_position
        assert len(conflict["observations"]) == 1
        assert db.item.normalization_summary["authors"]["status"] == "COMPLETED"
    assert db.links[0].author_order == 2
