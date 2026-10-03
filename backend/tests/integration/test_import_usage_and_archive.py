"""Integration tests for M2.6A follow-up import usage + safe history archive.

Covers:
- truthful import usage state (in_use, publication_source_links, author_variant_links)
- can_delete rules: ACTIVE=false, TERMINAL+in_use=false, TERMINAL+not_in_use=true
- DELETE re-checks dependencies and returns 409 with counts
- archive / restore-history endpoints
- archive state hidden from default list, returned with include_archived=true
- archive idempotency
- lecturer dataset behavior unchanged
- archive/restore as append-only audit events
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import Session, sessionmaker

import app.services.scopus_import_service as svc
from app.core.config import settings
from app.core.database import get_session
from app.core.security import password_hasher, token_service
from app.main import app
from app.models.base import Base
from app.models.governance import AuditEvent, User
from app.models.publication import (
    Publication,
    PublicationRawSource,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.models.scopus_raw import RawScopusRecord, ScopusImport


# ---------------------------------------------------------------------------
# Per-test isolated PostgreSQL schema (matches the project's existing pattern)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    url = settings.database_url
    schema = f"test_m26a_usage_{uuid.uuid4().hex}"
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
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    session.info["test_schema"] = schema
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="usage-admin@example.test",
        password_hash="fakehash",
        display_name="Usage Admin",
        role="ADMIN",
        lecturer_id=None,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth(user: User) -> dict[str, str]:
    token = token_service.create_access_token(
        {"sub": str(user.id), "email": user.email, "role": "ADMIN", "av": 1}
    )
    return {"Cookie": f"access_token={token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_import(
    db: Session,
    status: str = "STAGED",
    file_name: str = "test.csv",
) -> ScopusImport:
    item = ScopusImport(
        id=uuid.uuid4(),
        file_name=file_name,
        file_sha256="a" * 64,
        total_records=1,
        valid_records=1,
        invalid_records=0,
        status=status,
        error_summary=None,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(item)
    db.commit()
    return item


def _make_raw(
    db: Session,
    import_id: uuid.UUID,
    row_number: int,
    eid: str | None = "EID-1",
) -> RawScopusRecord:
    row = RawScopusRecord(
        id=uuid.uuid4(),
        import_id=import_id,
        row_number=row_number,
        row_hash="a" * 64,
        eid_raw=eid,
        doi_raw=None,
        raw_payload={"Title": f"Paper {row_number}"},
        validation_status="VALID",
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    return row


def _make_publication(db: Session, eid: str) -> Publication:
    pub = Publication(
        id=uuid.uuid4(),
        eid=eid,
        doi=None,
        title=f"Publication {eid}",
        title_normalized=f"publication {eid}".casefold(),
        year=2025,
        cited_by_count=0,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(pub)
    db.commit()
    return pub


def _link_publication(db: Session, pub_id: uuid.UUID, raw_id: uuid.UUID) -> None:
    db.add(PublicationRawSource(
        id=uuid.uuid4(),
        publication_id=pub_id,
        raw_record_id=raw_id,
        created_at=datetime.now(UTC),
    ))
    db.commit()


def _make_author_with_variant(
    db: Session, raw_id: uuid.UUID, name: str = "Smith J"
) -> tuple[ScopusAuthor, ScopusAuthorNameVariant]:
    author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id=f"sid-{uuid.uuid4().hex[:8]}",
        preferred_name=name,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(author)
    db.flush()
    variant = ScopusAuthorNameVariant(
        id=uuid.uuid4(),
        scopus_author_id=author.id,
        variant_type="AUTHOR_DISPLAY",
        variant_name=name,
        variant_name_normalized=name.casefold(),
        first_seen_raw_record_id=raw_id,
        created_at=datetime.now(UTC),
    )
    db.add(variant)
    db.commit()
    return author, variant


# ---------------------------------------------------------------------------
# 1. Terminal import with zero downstream refs
# ---------------------------------------------------------------------------


def test_terminal_import_with_zero_refs_is_deletable(
    db_session: Session, admin_user: User
) -> None:
    item = _make_import(db_session, status="STAGED")
    usage = svc.compute_usage_for_import(db_session, item.id)
    response = svc.to_import_response(
        item, performed_by=admin_user.display_name, usage=usage, archived=False
    )
    assert response.in_use is False
    assert response.can_delete is True
    assert response.usage == {"publication_source_links": 0, "author_variant_links": 0}


# ---------------------------------------------------------------------------
# 2. PublicationRawSource exists -> in_use + can_delete=False
# ---------------------------------------------------------------------------


def test_publication_source_link_marks_in_use(
    db_session: Session, admin_user: User
) -> None:
    item = _make_import(db_session)
    raw = _make_raw(db_session, item.id, 1)
    pub = _make_publication(db_session, "EID-1")
    _link_publication(db_session, pub.id, raw.id)

    usage = svc.compute_usage_for_import(db_session, item.id)
    assert usage.publication_source_links == 1
    assert usage.in_use is True
    response = svc.to_import_response(
        item, performed_by=admin_user.display_name, usage=usage
    )
    assert response.can_delete is False
    assert response.in_use is True


# ---------------------------------------------------------------------------
# 3. ScopusAuthorNameVariant first_seen_raw_record belongs to import
# ---------------------------------------------------------------------------


def test_author_variant_link_marks_in_use(
    db_session: Session, admin_user: User
) -> None:
    item = _make_import(db_session)
    raw = _make_raw(db_session, item.id, 1)
    _make_author_with_variant(db_session, raw.id)

    usage = svc.compute_usage_for_import(db_session, item.id)
    assert usage.author_variant_links == 1
    assert usage.in_use is True
    response = svc.to_import_response(
        item, performed_by=admin_user.display_name, usage=usage
    )
    assert response.can_delete is False


# ---------------------------------------------------------------------------
# 4. Both dependencies -> counts correct
# ---------------------------------------------------------------------------


def test_both_dependencies_counted(
    db_session: Session, admin_user: User
) -> None:
    item = _make_import(db_session)
    raw1 = _make_raw(db_session, item.id, 1)
    raw2 = _make_raw(db_session, item.id, 2)
    pub = _make_publication(db_session, "EID-1")
    _link_publication(db_session, pub.id, raw1.id)
    _make_author_with_variant(db_session, raw2.id)

    usage = svc.compute_usage_for_import(db_session, item.id)
    assert usage.publication_source_links == 1
    assert usage.author_variant_links == 1
    assert usage.in_use is True


# ---------------------------------------------------------------------------
# 5. Active import -> can_delete=False
# ---------------------------------------------------------------------------


def test_active_import_cannot_be_deleted(
    db_session: Session, admin_user: User
) -> None:
    item = _make_import(db_session, status="RECEIVED")
    usage = svc.compute_usage_for_import(db_session, item.id)
    response = svc.to_import_response(
        item, performed_by=admin_user.display_name, usage=usage
    )
    assert response.can_delete is False
    assert response.is_terminal is False


# ---------------------------------------------------------------------------
# 6. DELETE unused terminal import -> success
# ---------------------------------------------------------------------------


def test_delete_unused_terminal_import_succeeds(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session)
    headers = _auth(admin_user)
    response = client.delete(f"/api/v1/imports/{item.id}", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("deleted") is True


# ---------------------------------------------------------------------------
# 7. DELETE used import -> 409 IMPORT_IN_USE with counts
# ---------------------------------------------------------------------------


def test_delete_used_import_returns_409_with_counts(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session)
    raw = _make_raw(db_session, item.id, 1)
    pub = _make_publication(db_session, "EID-1")
    _link_publication(db_session, pub.id, raw.id)
    _make_author_with_variant(db_session, raw.id)

    headers = _auth(admin_user)
    response = client.delete(f"/api/v1/imports/{item.id}", headers=headers)
    assert response.status_code == 409
    body = response.json()
    assert body.get("code") == "IMPORT_IN_USE"
    # APIError.data is merged into the top-level response by the global handler.
    assert body.get("publication_source_links") == 1
    assert body.get("author_variant_links") == 1


# ---------------------------------------------------------------------------
# 8. Stale race: GET says deletable, downstream created, DELETE must re-check
# ---------------------------------------------------------------------------


def test_stale_delete_race_rechecks_dependencies(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session)
    headers = _auth(admin_user)
    # First read says deletable
    detail = client.get(f"/api/v1/imports/{item.id}", headers=headers).json()
    assert detail["can_delete"] is True
    # Downstream provenance arrives
    raw = _make_raw(db_session, item.id, 1)
    pub = _make_publication(db_session, "EID-1")
    _link_publication(db_session, pub.id, raw.id)
    # DELETE must now refuse
    response = client.delete(f"/api/v1/imports/{item.id}", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "IMPORT_IN_USE"


# ---------------------------------------------------------------------------
# 9. Archive unused import -> audit appended, rows preserved
# ---------------------------------------------------------------------------


def test_archive_unused_import_appends_audit(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session, file_name="to-archive.csv")
    headers = _auth(admin_user)
    response = client.post(f"/api/v1/imports/{item.id}/archive", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["archived"] is True

    db_session.expire_all()
    assert db_session.query(ScopusImport).filter(ScopusImport.id == item.id).one_or_none() is not None
    audit = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "scopus_imports",
            AuditEvent.entity_id == item.id,
            AuditEvent.action == "SCOPUS_IMPORT_HISTORY_ARCHIVED",
        )
        .one()
    )
    assert audit.actor_user_id == admin_user.id
    assert audit.before_state == {"archived": False}
    assert audit.after_state == {"archived": True}
    meta = audit.event_metadata or {}
    assert meta.get("filename") == "to-archive.csv"
    assert "in_use" in meta
    assert "publication_source_links" in meta
    assert "author_variant_links" in meta


# ---------------------------------------------------------------------------
# 10. Archive used import -> rows preserved, no destructive action
# ---------------------------------------------------------------------------


def test_archive_used_import_preserves_provenance(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session)
    raw = _make_raw(db_session, item.id, 1)
    pub = _make_publication(db_session, "EID-1")
    _link_publication(db_session, pub.id, raw.id)
    headers = _auth(admin_user)

    response = client.post(f"/api/v1/imports/{item.id}/archive", headers=headers)
    assert response.status_code == 200

    db_session.expire_all()
    # All provenance rows must still exist.
    assert db_session.query(ScopusImport).filter(ScopusImport.id == item.id).one()
    assert db_session.query(Publication).filter(Publication.id == pub.id).one()
    assert db_session.query(PublicationRawSource).count() == 1
    assert db_session.query(RawScopusRecord).count() == 1


# ---------------------------------------------------------------------------
# 11. Archived import excluded from default list
# ---------------------------------------------------------------------------


def test_archived_excluded_from_default_list(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session)
    headers = _auth(admin_user)
    client.post(f"/api/v1/imports/{item.id}/archive", headers=headers)

    response = client.get("/api/v1/imports", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(i["id"] != str(item.id) for i in items)


# ---------------------------------------------------------------------------
# 12. include_archived=true returns archived import
# ---------------------------------------------------------------------------


def test_include_archived_returns_archived(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session)
    headers = _auth(admin_user)
    client.post(f"/api/v1/imports/{item.id}/archive", headers=headers)

    response = client.get("/api/v1/imports?include_archived=true", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(i["id"] == str(item.id) and i["archived"] is True for i in items)


# ---------------------------------------------------------------------------
# 13. restore-history returns import to default list
# ---------------------------------------------------------------------------


def test_restore_history_returns_to_default_list(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session)
    headers = _auth(admin_user)
    client.post(f"/api/v1/imports/{item.id}/archive", headers=headers)
    response = client.post(
        f"/api/v1/imports/{item.id}/restore-history", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["archived"] is False

    listed = client.get("/api/v1/imports", headers=headers).json()["items"]
    assert any(i["id"] == str(item.id) for i in listed)


# ---------------------------------------------------------------------------
# 14. Repeated archive is safe/idempotent
# ---------------------------------------------------------------------------


def test_repeated_archive_is_idempotent(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session)
    headers = _auth(admin_user)
    client.post(f"/api/v1/imports/{item.id}/archive", headers=headers)
    client.post(f"/api/v1/imports/{item.id}/archive", headers=headers)
    db_session.expire_all()
    audit_count = (
        db_session.query(func.count(AuditEvent.id))
        .filter(
            AuditEvent.entity_type == "scopus_imports",
            AuditEvent.entity_id == item.id,
            AuditEvent.action == "SCOPUS_IMPORT_HISTORY_ARCHIVED",
        )
        .scalar()
    )
    assert audit_count == 1


# ---------------------------------------------------------------------------
# 15. Repeated restore is safe/idempotent
# ---------------------------------------------------------------------------


def test_repeated_restore_is_idempotent(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    item = _make_import(db_session)
    headers = _auth(admin_user)
    client.post(f"/api/v1/imports/{item.id}/archive", headers=headers)
    client.post(f"/api/v1/imports/{item.id}/restore-history", headers=headers)
    client.post(f"/api/v1/imports/{item.id}/restore-history", headers=headers)
    db_session.expire_all()
    audit_count = (
        db_session.query(func.count(AuditEvent.id))
        .filter(
            AuditEvent.entity_type == "scopus_imports",
            AuditEvent.entity_id == item.id,
            AuditEvent.action == "SCOPUS_IMPORT_HISTORY_RESTORED",
        )
        .scalar()
    )
    assert audit_count == 1


# ---------------------------------------------------------------------------
# 16. Lecturer dataset behavior unchanged
# ---------------------------------------------------------------------------


def test_lecturer_import_behavior_unchanged(
    db_session: Session, client: TestClient, admin_user: User
) -> None:
    """Lecturer import JSON entries still surface as LECTURERS, with
    can_delete driven by rollback status (not by in_use)."""
    from app.schemas.scopus_import import ScopusImportResponse

    response = ScopusImportResponse(
        id=uuid.uuid4(),
        type="LECTURERS",
        file_name="ictu_lecturers.json",
        status="IMPORTED",
        total_records=410,
        imported_records=410,
        failed_records=0,
        processed_records=410,
        progress_percent=100,
        duplicate_candidates=0,
        row_errors=[],
        error_summary=None,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        duration_seconds=0,
        is_terminal=True,
        performed_by="Admin",
        can_delete=False,
        in_use=False,
        archived=False,
        usage={"publication_source_links": 0, "author_variant_links": 0},
        lecturer_summary={
            "created": 410,
            "updated": 0,
            "unchanged": 0,
            "conflicts": 0,
            "warnings": 0,
            "dataset_name": "ictu_lecturers",
            "schema_version": "1.0",
        },
    )
    assert response.type == "LECTURERS"
    assert response.can_delete is False
    assert response.in_use is False
    # Lecturer can_delete should still be governed by rollback state, not usage.


# ---------------------------------------------------------------------------
# Bulk-aggregation avoids N+1
# ---------------------------------------------------------------------------


def test_compute_usage_for_imports_uses_bulk_queries(
    db_session: Session, admin_user: User
) -> None:
    item1 = _make_import(db_session, file_name="a.csv")
    item2 = _make_import(db_session, file_name="b.csv")
    raw1 = _make_raw(db_session, item1.id, 1, "EID-A")
    pub1 = _make_publication(db_session, "EID-A")
    _link_publication(db_session, pub1.id, raw1.id)

    usage_map = svc.compute_usage_for_imports(db_session, [item1.id, item2.id])
    assert usage_map[item1.id].publication_source_links == 1
    assert usage_map[item1.id].author_variant_links == 0
    assert usage_map[item2.id].publication_source_links == 0
    assert usage_map[item2.id].author_variant_links == 0
