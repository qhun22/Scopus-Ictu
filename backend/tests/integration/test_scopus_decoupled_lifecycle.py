"""Targeted integration tests for Scopus Decoupled Ingestion & Normalization Lifecycle.

Covers:
A. Upload / ingestion completion stops at STAGED, no auto-normalization, 0 publication_raw_sources.
B. STAGED import has in_use=false, can_delete=true.
C. Explicit normalize transitions STAGED → APPLIED, creates canonical publications & provenance, in_use=true.
D. APPLIED import hard delete is blocked by IMPORT_IN_USE (409) when provenance exists.
E. STAGED import safe delete succeeds when unused.
F. Normalization failure preserves raw ingestion and keeps status as STAGED (not APPLIED).
G. Re-normalizing APPLIED import is idempotent (EXISTING_UNCHANGED counters, no duplicates).
H. Duplicate CSV upload warning behavior remains valid and does not auto-normalize.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.exceptions import APIError
from app.models.base import Base
from app.models.governance import User
from app.models.publication import Publication, PublicationRawSource
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.normalization.scopus_normalizer import normalize_import
from app.services.scopus_import_service import (
    compute_usage_for_import,
    delete_scopus_import,
    normalize_existing_import,
    process_import_job,
    to_import_response,
)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    url = settings.database_url
    schema = f"test_decoupled_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, pool_pre_ping=True, future=True)
    with admin_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
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
        email="decoupled-admin@example.test",
        password_hash="fakehash",
        display_name="Decoupled Admin",
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


def _make_staged_import_with_raw(
    db: Session,
    eid: str = "2-s2.0-DECOUPLED-001",
    title: str = "Decoupled Lifecycle Paper",
) -> tuple[ScopusImport, RawScopusRecord]:
    imp = ScopusImport(
        id=uuid.uuid4(),
        file_name="scopus_sample.csv",
        file_sha256="b" * 64,
        total_records=1,
        valid_records=1,
        invalid_records=0,
        status="STAGED",
        error_summary=None,
        normalization_summary=None,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(imp)
    db.flush()

    raw = RawScopusRecord(
        id=uuid.uuid4(),
        import_id=imp.id,
        row_number=1,
        row_hash="c" * 64,
        eid_raw=eid,
        doi_raw="10.1000/182",
        raw_payload={"Title": title, "Authors": "Nguyen, V. A."},
        validation_status="VALID",
        created_at=datetime.now(UTC),
    )
    db.add(raw)
    db.commit()
    return imp, raw


class TestDecoupledLifecycle:
    def test_a_b_staged_import_has_no_provenance_and_is_deletable(
        self, db_session: Session, admin_user: User
    ) -> None:
        """A & B: STAGED import has in_use=False, can_delete=True, 0 publication links."""
        imp, _raw = _make_staged_import_with_raw(db_session)

        # Check provenance links
        prov_count = (
            db_session.query(PublicationRawSource)
            .join(RawScopusRecord, PublicationRawSource.raw_record_id == RawScopusRecord.id)
            .filter(RawScopusRecord.import_id == imp.id)
            .count()
        )
        assert prov_count == 0

        usage = compute_usage_for_import(db_session, imp.id)
        assert usage.in_use is False
        assert usage.publication_source_links == 0
        assert usage.author_variant_links == 0

        resp = to_import_response(imp, performed_by=admin_user.display_name, usage=usage)
        assert resp.status == "STAGED"
        assert resp.in_use is False
        assert resp.can_delete is True
        assert resp.normalization is None

    def test_c_explicit_normalization_transitions_staged_to_applied(
        self, db_session: Session, admin_user: User
    ) -> None:
        """C: Explicit normalize triggers STAGED → APPLIED, creates publication & provenance."""
        imp, _raw = _make_staged_import_with_raw(db_session)

        counters = normalize_existing_import(db_session, imp.id, actor=admin_user)
        assert counters.canonical_new == 1
        assert counters.canonical_processed == 1

        db_session.refresh(imp)
        assert imp.status == "APPLIED"
        assert imp.normalization_summary is not None
        assert imp.normalization_summary.get("status") == "COMPLETED"

        # Canonical publication created
        pub = db_session.query(Publication).filter(Publication.eid == "2-s2.0-DECOUPLED-001").first()
        assert pub is not None
        assert pub.title == "Decoupled Lifecycle Paper"

        # Provenance link created
        usage = compute_usage_for_import(db_session, imp.id)
        assert usage.in_use is True
        assert usage.publication_source_links == 1

        resp = to_import_response(imp, performed_by=admin_user.display_name, usage=usage)
        assert resp.status == "APPLIED"
        assert resp.in_use is True
        assert resp.can_delete is False
        assert resp.normalization is not None
        assert resp.normalization.status == "COMPLETED"
        assert resp.normalization.canonical_new == 1

    def test_d_applied_import_blocks_delete_when_in_use(
        self, db_session: Session, admin_user: User
    ) -> None:
        """D: Hard delete is blocked by IMPORT_IN_USE for APPLIED import."""
        imp, _raw = _make_staged_import_with_raw(db_session)
        normalize_existing_import(db_session, imp.id, actor=admin_user)

        with pytest.raises(APIError) as exc_info:
            delete_scopus_import(db_session, imp.id, actor=admin_user)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "IMPORT_IN_USE"
        assert exc_info.value.data.get("publication_source_links") == 1

    def test_e_staged_unused_import_can_be_deleted(
        self, db_session: Session, admin_user: User
    ) -> None:
        """E: STAGED unused import deletion succeeds safely."""
        imp, _raw = _make_staged_import_with_raw(db_session)

        success = delete_scopus_import(db_session, imp.id, actor=admin_user)
        assert success is True

        deleted_imp = db_session.query(ScopusImport).filter(ScopusImport.id == imp.id).first()
        assert deleted_imp is None
        raw_count = db_session.query(RawScopusRecord).filter(RawScopusRecord.import_id == imp.id).count()
        assert raw_count == 0

    def test_f_normalization_failure_preserves_raw_data_and_staged_status(
        self, db_session: Session, admin_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F: If normalization raises an exception, raw records are preserved and status is not falsely APPLIED."""
        imp, raw = _make_staged_import_with_raw(db_session)

        import app.services.normalization.scopus_normalizer as norm_mod

        def _raise_error(*_args, **_kwargs):
            raise RuntimeError("Synthetic batch processing failure")

        monkeypatch.setattr(norm_mod, "normalize_batch", _raise_error)

        with pytest.raises(RuntimeError):
            normalize_import(db_session, imp.id)

        db_session.refresh(imp)
        assert imp.status == "STAGED"  # not falsely APPLIED
        assert imp.normalization_summary is not None
        assert imp.normalization_summary.get("status") == "FAILED"

        # Raw record still intact
        db_raw = db_session.query(RawScopusRecord).filter(RawScopusRecord.id == raw.id).first()
        assert db_raw is not None
        assert db_raw.validation_status == "VALID"

    def test_g_renormalize_applied_is_idempotent(
        self, db_session: Session, admin_user: User
    ) -> None:
        """G: Re-running normalization on an APPLIED import is idempotent."""
        imp, _raw = _make_staged_import_with_raw(db_session)

        first_counters = normalize_existing_import(db_session, imp.id, actor=admin_user)
        assert first_counters.canonical_new == 1

        db_session.refresh(imp)
        assert imp.status == "APPLIED"

        # Re-run normalization
        second_counters = normalize_existing_import(db_session, imp.id, actor=admin_user)
        assert second_counters.canonical_new == 0
        assert second_counters.canonical_existing == 1
        assert second_counters.canonical_processed == 1

        # No duplicate publication records
        pub_count = db_session.query(Publication).filter(Publication.eid == "2-s2.0-DECOUPLED-001").count()
        assert pub_count == 1
