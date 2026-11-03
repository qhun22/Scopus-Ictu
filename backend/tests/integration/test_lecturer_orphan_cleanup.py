"""Rolling back every lecturer import must leave no imported lecturer behind (real PostgreSQL).

Reproduces the reported fault: import A creates the lecturers, an identical import B follows, A is
rolled back (B still covers them, so they stay), then B is rolled back. Nothing covers the lecturers
any more, so they must go too. Synthetic data only.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text

from app.models.audit import AuditEvent
from app.models.governance import User
from app.models.master_lecturer import Lecturer, LecturerSourceSnapshot
from app.services.lecturer_dataset.rollback import (
    LecturerRollbackService,
    find_orphaned_imported_lecturers,
)
from tests.conftest import disable_append_only_triggers
from tests.integration.test_affiliation_override_api import db  # noqa: F401  (fixture)


def _reset(db):
    with disable_append_only_triggers(db):
        db.execute(text("TRUNCATE lecturers CASCADE"))
    db.execute(text("DELETE FROM audit_events WHERE entity_type = 'lecturer_dataset'"))
    db.execute(text("DELETE FROM users WHERE email = 'orphan-admin@example.invalid'"))
    db.commit()


def _lecturer(db, name: str) -> Lecturer:
    lecturer = Lecturer(full_name=name, full_name_normalized=name.lower())
    db.add(lecturer)
    db.flush()
    return lecturer


def _snapshot(db, lecturer: Lecturer, *, system: str = "ictu_dspace_archive") -> LecturerSourceSnapshot:
    snap = LecturerSourceSnapshot(
        lecturer_id=lecturer.id, source_system=system, source_url="https://example.invalid/x",
        snapshot_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(), raw_payload={"canonical": {}},
        parser_version="test", validation_status="VALID", fetched_at=datetime.now(UTC),
    )
    db.add(snap)
    db.flush()
    return snap


def _import(db, admin, *, created: list[Lecturer], snaps: list[LecturerSourceSnapshot]) -> AuditEvent:
    audit = AuditEvent(
        entity_type="lecturer_dataset", entity_id=uuid.uuid4(), action="LECTURER_DATASET_IMPORTED",
        actor_type="USER", actor_user_id=admin.id, before_state=None,
        after_state={"status": "IMPORTED", "created": len(created), "record_count": len(snaps)},
        event_metadata={
            "filename": "synthetic.json",
            "created_lecturer_ids": [str(x.id) for x in created],
            "snapshot_ids": [str(s.id) for s in snaps],
        },
    )
    db.add(audit)
    db.flush()
    return audit


def _admin(db) -> User:
    admin = User(email="orphan-admin@example.invalid", password_hash="x", display_name="Admin", role="ADMIN")
    db.add(admin)
    db.flush()
    return admin


def test_rolling_back_the_creator_then_the_later_import_removes_the_lecturers(db):
    _reset(db)
    admin = _admin(db)
    people = [_lecturer(db, f"Synthetic Lecturer {n}") for n in range(3)]
    import_a = _import(db, admin, created=people, snaps=[_snapshot(db, p) for p in people])
    import_b = _import(db, admin, created=[], snaps=[_snapshot(db, p) for p in people])
    db.commit()
    service = LecturerRollbackService()

    service.rollback_import(db, import_id=import_a.id, actor=admin)
    assert db.scalar(text("SELECT count(*) FROM lecturers")) == 3        # B still covers them
    assert find_orphaned_imported_lecturers(db) == set()

    service.rollback_import(db, import_id=import_b.id, actor=admin)
    assert db.scalar(text("SELECT count(*) FROM lecturers")) == 0        # nothing covers them now


def test_a_manual_lecturer_is_never_removed(db):
    _reset(db)
    admin = _admin(db)
    imported = _lecturer(db, "Synthetic Imported")
    manual = _lecturer(db, "Synthetic Manual")
    import_a = _import(db, admin, created=[imported], snaps=[_snapshot(db, imported), _snapshot(db, manual)])
    db.commit()

    LecturerRollbackService().rollback_import(db, import_id=import_a.id, actor=admin)
    names = set(db.scalars(select(Lecturer.full_name)).all())
    assert names == {"Synthetic Manual"}


def test_orphans_left_by_the_old_behaviour_are_found_and_purged(db):
    _reset(db)
    admin = _admin(db)
    orphan = _lecturer(db, "Synthetic Orphan")
    craw_only = _lecturer(db, "Synthetic Craw Only")
    covered = _lecturer(db, "Synthetic Covered")
    manual = _lecturer(db, "Synthetic Manual")
    _snapshot(db, craw_only, system="ictu_craw")            # Craw data does not "cover" a lecturer
    _snapshot(db, covered)                                  # an import snapshot does
    _import(db, admin, created=[orphan, craw_only, covered], snaps=[])
    db.commit()

    assert find_orphaned_imported_lecturers(db) == {orphan.id, craw_only.id}
    assert LecturerRollbackService().purge_orphans(db, actor=admin) == 2
    remaining = set(db.scalars(select(Lecturer.full_name)).all())
    assert remaining == {"Synthetic Covered", "Synthetic Manual"}
    assert LecturerRollbackService().purge_orphans(db, actor=admin) == 0     # idempotent
