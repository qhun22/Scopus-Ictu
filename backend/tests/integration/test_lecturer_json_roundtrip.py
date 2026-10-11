"""Official JSON cycle: import v1 -> edit -> export v2 -> preview/import v2.

These tests run against a real PostgreSQL schema (one disposable schema per
test, created from the ORM metadata) so that identity matching, unique
indexes, snapshots and the export query are exercised for real.
"""

from __future__ import annotations

import copy
import json
import os
import uuid
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.models.governance import AuditEvent, User
from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)
from app.services.lecturer_dataset.parser import parse_and_validate

SOURCE_SYSTEM = "ictu_dspace_archive"
BASE_URL = "https://repository.example.test/giang-vien/"


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for JSON round-trip tests")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("round-trip tests must never target an acceptance database")

    schema = f"test_json_roundtrip_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, pool_pre_ping=True, future=True)
    with admin_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url, pool_pre_ping=True, future=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    admin = User(
        id=uuid.uuid4(), email="admin@roundtrip.test", password_hash="x",
        display_name="Admin", role="ADMIN", is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def make_dataset(n: int = 6) -> dict[str, Any]:
    lecturers = []
    for i in range(n):
        slug = f"giang-vien-{i}"
        lecturers.append({
            "source_id": f"{BASE_URL}{slug}/",
            "staff_code": f"CB{i:03d}" if i % 2 == 0 else None,
            "full_name": f"Giảng Viên {i}",
            "full_name_normalized": f"giảng viên {i}",
            "institutional_email": f"gv{i}@example.test",
            "tel": f"090000000{i}",
            "academic_degree": "ThS",
            "academic_rank": None,
            "position": None,
            "faculty": None,
            "department": f"Bộ môn {i}",
            "profile_url": f"{BASE_URL}{slug}/",
            "orcid": f"0000-0000-0000-000{i}" if i < 3 else None,
            "is_active": True,
            "provenance": {
                "source_name": "ICTU DSpace (test)",
                "source_system": SOURCE_SYSTEM,
                "source_urls": [BASE_URL],
                "source_record_id": f"{BASE_URL}{slug}/",
                "retrieved_at": "2026-10-02T02:24:04+00:00",
                "parser_version": "dspace_parser/1.0",
                "known_specialisation": f"Chuyên ngành {i}",
            },
            "known_publications": [],
        })
    return {
        "dataset": {
            "name": "ICTU Lecturer Master Dataset",
            "schema_version": "1.0",
            "institution": "ICTU",
            "source": "ICTU official DSpace repository",
            "source_url": BASE_URL,
            "source_system": SOURCE_SYSTEM,
            "generated_at": "2026-10-08T12:11:17+00:00",
            "parser_version": "merge/1.0",
            "record_count": n,
        },
        "lecturers": lecturers,
    }


def to_bytes(dataset: dict) -> bytes:
    dataset = copy.deepcopy(dataset)
    dataset["dataset"]["record_count"] = len(dataset["lecturers"])
    return json.dumps(dataset, ensure_ascii=False).encode("utf-8")


def post(client: TestClient, path: str, dataset: dict | bytes):
    content = dataset if isinstance(dataset, bytes) else to_bytes(dataset)
    return client.post(f"/api/v1/lecturers/{path}", files={"file": ("d.json", content, "application/json")})


def lecturer_ids(db: Session) -> dict[str, uuid.UUID]:
    return {r.email: r.id for r in db.execute(select(Lecturer)).scalars() if r.email}


def count(db: Session, model) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


def import_v1(client: TestClient, n: int = 6) -> dict[str, Any]:
    ds = make_dataset(n)
    resp = post(client, "import", ds)
    assert resp.status_code == 201, resp.text
    assert resp.json()["summary"]["created"] == n
    return ds


def export(client: TestClient) -> dict[str, Any]:
    resp = client.get("/api/v1/lecturers/export")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Ca A / Ca E — re-import without edits, preservation
# ---------------------------------------------------------------------------

def test_export_then_reimport_preserves_identity(client: TestClient, db_session: Session) -> None:
    v1 = import_v1(client)
    # Synthetic demo lecturer without ICTU source identity must not be exported.
    db_session.add(Lecturer(id=uuid.uuid4(), full_name="Người dùng", full_name_normalized="người dùng",
                            email="user@synthetic.test"))
    db_session.commit()
    ids_before = {r.id for r in db_session.execute(select(Lecturer)).scalars()}
    lecturers_before = count(db_session, Lecturer)

    v2 = export(client)
    assert len(v2["lecturers"]) == 6
    assert [r["source_id"] for r in v2["lecturers"]] == sorted(r["source_id"] for r in v1["lecturers"])
    assert {r["source_id"] for r in v2["lecturers"]} == {r["source_id"] for r in v1["lecturers"]}
    assert "user@synthetic.test" not in json.dumps(v2)

    # Parser round trip + metadata about what PostgreSQL does not preserve.
    envelope = parse_and_validate(json.dumps(v2).encode("utf-8"))
    assert len(envelope["lecturers"]) == 6
    assert v2["dataset"]["export"]["not_preserved_fields"] == ["tel", "google_scholar"]
    assert all("tel" not in r for r in v2["lecturers"])
    # Original provenance kept, export info added.
    sample = v2["lecturers"][0]["provenance"]
    assert sample["source_record_id"] == v2["lecturers"][0]["source_id"]
    assert sample["parser_version"] == "dspace_parser/1.0"
    assert sample["known_specialisation"].startswith("Chuyên ngành")
    assert sample["export"]["exporter"]
    # No credential / account material.
    blob = json.dumps(v2).lower()
    for forbidden in ("password", "token", "jwt", "cookie", "secret", "auth_version", "user_id"):
        assert forbidden not in blob

    snapshots_before = count(db_session, LecturerSourceSnapshot)
    preview = post(client, "import/preview", v2)
    assert preview.status_code == 200, preview.text
    summary = preview.json()["summary"]
    assert (summary["create"], summary["update"], summary["unchanged"]) == (0, 0, 6)
    assert summary["blocking_conflicts"] == 0 and summary["deleted"] == 0
    assert count(db_session, LecturerSourceSnapshot) == snapshots_before  # preview is read-only

    resp = post(client, "import", v2)
    assert resp.status_code == 201, resp.text
    assert resp.json()["summary"]["created"] == 0
    assert resp.json()["summary"]["updated"] == 0
    assert count(db_session, Lecturer) == lecturers_before
    assert {r.id for r in db_session.execute(select(Lecturer)).scalars()} == ids_before
    # Append-only history: one new snapshot per record, no new canonical lecturer.
    assert count(db_session, LecturerSourceSnapshot) == snapshots_before + 6

    # v3 can be exported again with identical identities.
    v3 = export(client)
    assert [r["source_id"] for r in v3["lecturers"]] == [r["source_id"] for r in v2["lecturers"]]
    assert [r["provenance"]["source_record_id"] for r in v3["lecturers"]] == \
        [r["provenance"]["source_record_id"] for r in v2["lecturers"]]


def test_source_id_is_never_the_internal_uuid(client: TestClient, db_session: Session) -> None:
    import_v1(client)
    internal = {str(i) for i in lecturer_ids(db_session).values()}
    for record in export(client)["lecturers"]:
        assert record["source_id"] not in internal
        assert record["source_id"].startswith(BASE_URL)


def test_uuid_source_id_is_rejected(client: TestClient) -> None:
    ds = make_dataset(2)
    ds["lecturers"][0]["source_id"] = str(uuid.uuid4())
    ds["lecturers"][0]["provenance"]["source_record_id"] = None
    resp = post(client, "import/preview", ds)
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_SOURCE_ID"


def test_duplicate_source_id_or_orcid_in_file_is_rejected(client: TestClient) -> None:
    ds = make_dataset(3)
    ds["lecturers"][1]["source_id"] = ds["lecturers"][0]["source_id"]
    resp = post(client, "import/preview", ds)
    assert resp.status_code == 422 and resp.json()["code"] == "DUPLICATE_LECTURER_IDENTITY"
    ds = make_dataset(3)
    ds["lecturers"][1]["orcid"] = ds["lecturers"][0]["orcid"]
    resp = post(client, "import/preview", ds)
    assert resp.status_code == 422 and resp.json()["code"] == "DUPLICATE_LECTURER_IDENTITY"


# ---------------------------------------------------------------------------
# Ca B — edit through the official API, export v2, import v2
# ---------------------------------------------------------------------------

def test_edit_export_import_keeps_uuid_and_count(client: TestClient, db_session: Session) -> None:
    import_v1(client)
    ids = lecturer_ids(db_session)
    target = db_session.get(Lecturer, ids["gv3@example.test"])
    resp = client.patch(
        f"/api/v1/lecturers/{target.id}",
        json={"version": target.version, "position": "QA-ROUNDTRIP-POSITION"},
    )
    assert resp.status_code == 200, resp.text

    v2 = export(client)
    edited = [r for r in v2["lecturers"] if r["institutional_email"] == "gv3@example.test"][0]
    assert edited["position"] == "QA-ROUNDTRIP-POSITION"
    assert edited["source_id"] == f"{BASE_URL}giang-vien-3/"

    summary = post(client, "import/preview", v2).json()["summary"]
    assert (summary["create"], summary["update"], summary["unchanged"]) == (0, 0, 6)

    # A file carrying a different value is an update of the same lecturer.
    changed = copy.deepcopy(v2)
    for r in changed["lecturers"]:
        if r["institutional_email"] == "gv3@example.test":
            r["position"] = "Giảng viên chính"
    assert post(client, "import/preview", changed).json()["summary"]["update"] == 1
    assert post(client, "import", changed).json()["summary"]["updated"] == 1
    assert count(db_session, Lecturer) == 6
    assert lecturer_ids(db_session) == ids
    assert db_session.get(Lecturer, target.id).position == "Giảng viên chính"
    # Import v2 itself (the edited export) is a no-op on canonical data.
    assert post(client, "import", v2).json()["summary"]["updated"] == 1  # reverts file value
    assert db_session.get(Lecturer, target.id).position == "QA-ROUNDTRIP-POSITION"
    assert count(db_session, Lecturer) == 6 and lecturer_ids(db_session) == ids


# ---------------------------------------------------------------------------
# Ca C — e-mail change is recognised through source_id
# ---------------------------------------------------------------------------

def test_email_change_is_matched_by_source_id(client: TestClient, db_session: Session) -> None:
    import_v1(client)
    ids = lecturer_ids(db_session)
    changed = make_dataset(6)
    changed["lecturers"][1]["institutional_email"] = "new.mail1@example.test"
    preview = post(client, "import/preview", changed).json()
    assert preview["summary"]["update"] == 1 and preview["summary"]["create"] == 0
    assert preview["summary"]["blocking_conflicts"] == 0
    assert post(client, "import", changed).status_code == 201
    assert count(db_session, Lecturer) == 6
    assert db_session.get(Lecturer, ids["gv1@example.test"]).email == "new.mail1@example.test"


def test_email_owned_by_another_lecturer_is_a_blocking_conflict(client: TestClient, db_session: Session) -> None:
    import_v1(client)
    ids = lecturer_ids(db_session)
    changed = make_dataset(6)
    changed["lecturers"][1]["institutional_email"] = "gv2@example.test"  # belongs to lecturer 2
    changed["lecturers"] = changed["lecturers"][:2]  # lecturer 2 is not in the file
    preview = post(client, "import/preview", changed)
    assert preview.status_code == 200
    body = preview.json()
    assert body["summary"]["blocking_conflicts"] == 1
    assert body["conflicts"][0]["blocking"] is True
    assert body["conflicts"][0]["matched_by"] == "source_id_email_conflict"

    snapshots = count(db_session, LecturerSourceSnapshot)
    audits = count(db_session, AuditEvent)
    resp = post(client, "import", changed)
    assert resp.status_code == 409
    assert resp.json()["code"] == "LECTURER_IDENTITY_CONFLICT"
    assert count(db_session, LecturerSourceSnapshot) == snapshots  # nothing written
    assert count(db_session, AuditEvent) == audits
    assert lecturer_ids(db_session) == ids


def test_source_id_staff_code_conflict_fails_closed(client: TestClient, db_session: Session) -> None:
    import_v1(client)
    changed = make_dataset(6)
    changed["lecturers"][1]["staff_code"] = "CB000"  # CB000 belongs to lecturer 0
    changed["lecturers"] = changed["lecturers"][1:2]
    assert post(client, "import/preview", changed).json()["conflicts"][0]["matched_by"] == "source_id_staff_code_conflict"
    assert post(client, "import", changed).status_code == 409


def test_staff_code_and_email_pointing_to_different_people_conflict(client: TestClient) -> None:
    import_v1(client)
    other = make_dataset(6)
    rec = other["lecturers"][2]
    rec["source_id"] = f"{BASE_URL}another/"
    rec["provenance"]["source_record_id"] = rec["source_id"]
    rec["profile_url"] = rec["source_id"]
    rec["orcid"] = None
    rec["institutional_email"] = "gv0@example.test"  # record 0's email, staff CB002 is record 2's
    other["lecturers"] = [rec]
    body = post(client, "import/preview", other).json()
    assert body["summary"]["blocking_conflicts"] == 1
    assert body["conflicts"][0]["matched_by"] == "staff_code_email_conflict"
    assert post(client, "import", other).status_code == 409


def test_matched_lecturer_bound_to_other_source_id_conflicts(client: TestClient, db_session: Session) -> None:
    import_v1(client)
    other = make_dataset(6)
    rec = other["lecturers"][1]
    rec["source_id"] = f"{BASE_URL}someone-else/"
    rec["provenance"]["source_record_id"] = rec["source_id"]
    rec["profile_url"] = rec["source_id"]
    other["lecturers"] = [rec]  # same e-mail as lecturer 1, different source identity
    body = post(client, "import/preview", other).json()
    assert body["conflicts"][0]["matched_by"] == "source_id_bound_elsewhere"
    assert post(client, "import", other).status_code == 409
    assert count(db_session, Lecturer) == 6


def test_orcid_owned_by_another_lecturer_is_blocking(client: TestClient, db_session: Session) -> None:
    import_v1(client)
    changed = make_dataset(6)
    changed["lecturers"][4]["orcid"] = changed["lecturers"][0]["orcid"]
    changed["lecturers"][0]["orcid"] = "0000-0000-0000-0009"  # keeps file-internal uniqueness
    body = post(client, "import/preview", changed).json()
    assert body["summary"]["blocking_conflicts"] >= 1
    assert any(c["matched_by"] == "orcid_conflict" for c in body["conflicts"])
    assert post(client, "import", changed).status_code == 409


def test_same_name_is_not_merged(client: TestClient, db_session: Session) -> None:
    import_v1(client)
    other = make_dataset(6)
    rec = copy.deepcopy(other["lecturers"][1])
    rec["source_id"] = f"{BASE_URL}namesake/"
    rec["provenance"]["source_record_id"] = rec["source_id"]
    rec["profile_url"] = rec["source_id"]
    rec["institutional_email"] = "namesake@example.test"
    rec["staff_code"] = None
    rec["orcid"] = None
    other["lecturers"] = [rec]
    body = post(client, "import/preview", other).json()
    assert body["summary"]["create"] == 1 and body["summary"]["blocking_conflicts"] == 0
    assert post(client, "import", other).status_code == 201
    assert count(db_session, Lecturer) == 7


# ---------------------------------------------------------------------------
# Ca D — absent lecturers are never deleted
# ---------------------------------------------------------------------------

def test_absent_record_is_not_deleted(client: TestClient, db_session: Session) -> None:
    import_v1(client)
    ids = lecturer_ids(db_session)
    absent_id = ids["gv5@example.test"]
    account = User(id=uuid.uuid4(), email="gv5-account@roundtrip.test", password_hash="x",
                   display_name="GV5", role="LECTURER", lecturer_id=absent_id, is_active=True)
    db_session.add(account)
    db_session.commit()

    partial = make_dataset(6)
    partial["lecturers"] = partial["lecturers"][:5]
    summary = post(client, "import/preview", partial).json()["summary"]
    assert summary["absent_from_file"] == 1
    assert summary["deleted"] == 0 and summary["create"] == 0

    assert post(client, "import", partial).status_code == 201
    assert count(db_session, Lecturer) == 6
    db_session.expire_all()
    assert db_session.get(Lecturer, absent_id) is not None
    assert db_session.get(User, account.id).lecturer_id == absent_id
    assert lecturer_ids(db_session) == ids


# ---------------------------------------------------------------------------
# Known publications / identities
# ---------------------------------------------------------------------------

def test_known_publications_roundtrip_without_duplicates(client: TestClient, db_session: Session) -> None:
    ds = make_dataset(2)
    ds["lecturers"][0]["known_publications"] = [{
        "title_raw": "A Paper", "title_normalized": "a paper",
        "doi_raw": None, "doi_normalized": None, "source_title_raw": "Journal", "published_year": 2024,
    }]
    assert post(client, "import", ds).status_code == 201
    v2 = export(client)
    exported = [r for r in v2["lecturers"] if r["institutional_email"] == "gv0@example.test"][0]
    assert [p["title_raw"] for p in exported["known_publications"]] == ["A Paper"]
    assert post(client, "import", v2).status_code == 201
    assert count(db_session, LecturerKnownPublication) == 1
    assert len(export(client)["lecturers"][0]["known_publications"]) + \
        len(export(client)["lecturers"][1]["known_publications"]) == 1


def test_export_requires_admin(client: TestClient, db_session: Session) -> None:
    lecturer_user = User(id=uuid.uuid4(), email="l@roundtrip.test", password_hash="x",
                         display_name="L", role="LECTURER", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: lecturer_user
    assert client.get("/api/v1/lecturers/export").status_code == 403


def test_export_of_empty_database_is_valid_but_not_importable(client: TestClient) -> None:
    v = export(client)
    assert v["dataset"]["record_count"] == 0 and v["lecturers"] == []


# ---------------------------------------------------------------------------
# Login accounts travel with the lecturer (export -> import, schema 1.1)
# ---------------------------------------------------------------------------

PASSWORD = "MatKhau@12345"


def _add_account(db: Session, lecturer_id: uuid.UUID, email: str, role: str, *, hasher=None) -> User:
    from app.core.security import PasswordHasher

    user = User(
        id=uuid.uuid4(), email=email, password_hash=(hasher or PasswordHasher()).hash(PASSWORD),
        display_name=f"Tài khoản {email}", role=role, lecturer_id=lecturer_id, is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _record_of(payload: dict, institutional_email: str) -> dict:
    return next(r for r in payload["lecturers"] if r["institutional_email"] == institutional_email)


def test_accounts_are_exported_and_restored_usable_after_reimport(
    client: TestClient, db_session: Session
) -> None:
    from app.core.security import PasswordHasher

    import_v1(client, 4)
    ids = lecturer_ids(db_session)
    wanted = {
        "gv0@example.test": ("acc0@example.test", "LECTURER"),
        "gv1@example.test": ("acc1@example.test", "REVIEWER"),
        "gv2@example.test": ("acc2@example.test", "ADMIN"),
    }
    originals = {
        lec_email: _add_account(db_session, ids[lec_email], acc_email, role)
        for lec_email, (acc_email, role) in wanted.items()
    }

    v2 = export(client)
    # Only lecturers that own an account carry the block; every role is kept.
    assert sum("account" in r for r in v2["lecturers"]) == 3
    assert "account" not in _record_of(v2, "gv3@example.test")
    for lec_email, (acc_email, role) in wanted.items():
        block = _record_of(v2, lec_email)["account"]
        assert block["email"] == acc_email and block["role"] == role and block["is_active"] is True
        assert block["password_hash"] == originals[lec_email].password_hash
        assert block["password_hash"].startswith("$argon2") and PASSWORD not in json.dumps(block)
    assert v2["dataset"]["export"]["includes_accounts"] is True
    assert v2["dataset"]["schema_version"] == "1.1"

    export_audit = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "LECTURER_DATASET_EXPORTED")
    ).scalars().all()[-1]
    assert export_audit.event_metadata["accounts_exported"] == 3
    assert "argon2" not in json.dumps(export_audit.event_metadata)

    # The accounts disappear (fresh system); re-importing the file brings them back, usable.
    for user in originals.values():
        db_session.delete(user)
    db_session.commit()
    assert count(db_session, User) == 1  # only the admin of the fixture

    resp = post(client, "import", v2)
    assert resp.status_code == 201, resp.text
    assert resp.json()["conflicts"] == []
    db_session.expire_all()
    for lec_email, (acc_email, role) in wanted.items():
        restored = db_session.scalar(select(User).where(User.email == acc_email))
        assert restored is not None and restored.role == role
        assert restored.lecturer_id == ids[lec_email] and restored.is_active is True
        assert restored.password_hash == originals[lec_email].password_hash
        assert PasswordHasher().verify(PASSWORD, restored.password_hash) is True  # same password logs in

    imported = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "LECTURER_DATASET_IMPORTED")
    ).scalars().all()[-1]
    assert imported.event_metadata["accounts_created"] == 3
    assert len(imported.event_metadata["created_user_ids"]) == 3
    assert "argon2" not in json.dumps([imported.event_metadata, imported.after_state])

    # Idempotent: importing again changes nothing and raises no warning.
    again = post(client, "import", v2)
    assert again.status_code == 201, again.text
    assert again.json()["conflicts"] == []
    assert count(db_session, User) == 4


def test_existing_account_email_only_warns_and_is_never_overwritten(
    client: TestClient, db_session: Session
) -> None:
    ds = import_v1(client, 3)
    ids = lecturer_ids(db_session)
    owner = _add_account(db_session, ids["gv0@example.test"], "shared@example.test", "LECTURER")
    original_hash, original_role = owner.password_hash, owner.role

    other_hash = _add_account(db_session, ids["gv2@example.test"], "tmp@example.test", "LECTURER").password_hash
    db_session.delete(db_session.scalar(select(User).where(User.email == "tmp@example.test")))
    db_session.commit()
    ds["lecturers"][1]["account"] = {
        "email": "Shared@Example.test", "role": "ADMIN", "password_hash": other_hash,
        "display_name": "Cố ghi đè", "is_active": True,
    }
    preview = post(client, "import/preview", ds)
    assert preview.status_code == 200, preview.text
    warnings = [c for c in preview.json()["conflicts"] if c["matched_by"] == "account_email"]
    assert len(warnings) == 1 and warnings[0]["blocking"] is False
    assert "đã được dùng" in warnings[0]["reason"]
    assert preview.json()["summary"]["blocking_conflicts"] == 0

    resp = post(client, "import", ds)
    assert resp.status_code == 201, resp.text  # a warning never blocks the import
    db_session.expire_all()
    kept = db_session.scalar(select(User).where(User.email == "shared@example.test"))
    assert kept.id == owner.id and kept.password_hash == original_hash and kept.role == original_role
    assert kept.lecturer_id == ids["gv0@example.test"]
    assert db_session.scalar(select(User).where(User.lecturer_id == ids["gv1@example.test"])) is None


def test_lecturer_that_already_has_another_account_is_not_given_a_second_one(
    client: TestClient, db_session: Session
) -> None:
    ds = import_v1(client, 2)
    ids = lecturer_ids(db_session)
    existing = _add_account(db_session, ids["gv0@example.test"], "first@example.test", "LECTURER")
    ds["lecturers"][0]["account"] = {
        "email": "second@example.test", "role": "REVIEWER",
        "password_hash": existing.password_hash, "display_name": "Thứ hai", "is_active": True,
    }
    resp = post(client, "import", ds)
    assert resp.status_code == 201, resp.text
    assert [c["matched_by"] for c in resp.json()["conflicts"]] == ["account_email"]
    db_session.expire_all()
    assert db_session.scalar(select(User).where(User.email == "second@example.test")) is None
    assert db_session.scalar(select(User).where(User.lecturer_id == ids["gv0@example.test"])).email == "first@example.test"


def test_account_block_with_plaintext_password_is_rejected_without_echo(client: TestClient) -> None:
    ds = make_dataset(2)
    ds["lecturers"][0]["account"] = {
        "email": "plain@example.test", "role": "LECTURER", "password_hash": "MatKhauChuThuong1",
        "display_name": "X", "is_active": True,
    }
    resp = post(client, "import/preview", ds)
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "INVALID_LECTURER_DATASET"
    assert "MatKhauChuThuong1" not in resp.text
