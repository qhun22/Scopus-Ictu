"""The school's lecturer data is mandatory before a Scopus CSV; identical files are flagged, not blocked."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.models.master_lecturer import Lecturer
from app.models.scopus_raw import ScopusImport
from app.services.scopus_import_service import duplicate_map
from tests.integration.test_affiliation_override_api import (  # noqa: F401  (fixtures)
    as_role,
    client,
    db,
)

CSV = b"EID,Title\n2-s2.0-000000000001,Synthetic\n"


def _upload(client):
    return client.post("/api/v1/imports/scopus", files={"file": ("synthetic.csv", CSV, "text/csv")})


def _clear(db):
    db.execute(text("TRUNCATE lecturers, scopus_imports CASCADE"))
    db.commit()


def test_a_scopus_csv_is_refused_until_lecturer_data_exists(client, as_role, db):
    _clear(db)
    as_role("ADMIN")

    prerequisites = client.get("/api/v1/imports/prerequisites").json()
    assert prerequisites == {"lecturer_count": 0, "scopus_import_ready": False}

    refused = _upload(client)
    assert refused.status_code == 409
    assert refused.json()["code"] == "LECTURER_DATA_REQUIRED"
    assert db.scalar(text("SELECT count(*) FROM scopus_imports")) == 0     # nothing was created


def test_prerequisites_turn_ready_once_a_lecturer_exists(client, as_role, db):
    _clear(db)
    db.add(Lecturer(full_name="TS. Synthetic Lecturer", full_name_normalized="ts. synthetic lecturer"))
    db.commit()
    as_role("ADMIN")
    assert client.get("/api/v1/imports/prerequisites").json() == {
        "lecturer_count": 1, "scopus_import_ready": True}


def test_prerequisites_are_admin_only(client, as_role, db):
    as_role("REVIEWER")
    assert client.get("/api/v1/imports/prerequisites").status_code == 403


def test_an_import_with_the_same_content_as_an_earlier_one_is_flagged_as_a_duplicate(db):
    _clear(db)
    digest = hashlib.sha256(CSV).hexdigest()
    now = datetime.now(UTC)

    def make(name: str, at: datetime) -> ScopusImport:
        item = ScopusImport(file_name=name, file_sha256=digest, total_records=1, valid_records=1,
                            invalid_records=0, status="STAGED", created_at=at, updated_at=at)
        db.add(item)
        db.flush()
        return item

    first = make("first.csv", now - timedelta(hours=1))
    second = make("second.csv", now)
    db.commit()

    flagged = duplicate_map(db, [first, second])
    assert first.id not in flagged                              # the original is not a duplicate
    assert flagged[second.id]["import_id"] == str(first.id)
    assert flagged[second.id]["file_name"] == "first.csv"


def _lecturer_import_audit(db, *, sha: str, at: datetime, actor_id, unchanged: int = 5):
    from app.models.audit import AuditEvent

    import uuid as _uuid

    audit = AuditEvent(
        entity_type="lecturer_dataset", entity_id=_uuid.uuid4(), action="LECTURER_DATASET_IMPORTED",
        actor_type="USER", actor_user_id=actor_id, before_state=None,
        after_state={"status": "IMPORTED", "created": 0, "updated": 0, "unchanged": unchanged,
                     "record_count": unchanged},
        event_metadata={"filename": "synthetic.json", "file_sha256": sha}, created_at=at,
    )
    db.add(audit)
    db.flush()
    return audit


def test_confirming_an_identical_lecturer_file_supersedes_the_earlier_import_without_rolling_back(db):
    from app.models.governance import User
    from app.services.scopus_import_service import list_imports, supersede_earlier_lecturer_imports

    _clear(db)
    db.execute(text("DELETE FROM users WHERE email = 'a@example.invalid'"))
    sha = hashlib.sha256(b"same lecturer file").hexdigest()
    now = datetime.now(UTC)
    admin = User(email="a@example.invalid", password_hash="x", display_name="Admin", role="ADMIN")
    db.add(admin)
    db.flush()
    older = _lecturer_import_audit(db, sha=sha, at=now - timedelta(hours=1), actor_id=admin.id)
    newest = _lecturer_import_audit(db, sha=sha, at=now, actor_id=admin.id)
    other = _lecturer_import_audit(db, sha=hashlib.sha256(b"different file").hexdigest(), at=now,
                                   actor_id=admin.id)
    db.commit()

    assert supersede_earlier_lecturer_imports(db, sha, admin) == 1
    assert supersede_earlier_lecturer_imports(db, sha, admin) == 0          # idempotent

    by_id = {item.id: item for item in list_imports(db)}
    assert by_id[older.id].status == "SUPERSEDED"
    assert by_id[newest.id].status == "IMPORTED"
    assert by_id[other.id].status == "IMPORTED"
    # "Loaded" counts every record now present, so an all-unchanged re-import reads 5 / 5, not 0 / 5.
    assert by_id[newest.id].imported_records == by_id[newest.id].total_records == 5
