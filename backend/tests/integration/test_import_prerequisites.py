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
