"""ADMIN online affiliation enrichment: trigger -> poll -> cancel, and preview/apply
against the resulting bundle via job_id (never a client-supplied path).

HTTP calls to OpenAlex/Crossref/ORCID are mocked via httpx2.MockTransport so
these tests run offline and deterministically; a dedicated manual script
(outside pytest) exercises the real network for the acceptance report.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models.affiliation_enrichment import AffiliationEnrichmentJob
from app.models.base import Base
from app.models.governance import User
from app.models.publication import Publication, PublicationAuthor, PublicationRawSource, ScopusAuthor
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services import affiliation_enrichment_service as enrichment
from app.services import affiliation_online_fetch

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("never target an acceptance database")
    schema = f"test_aff_enrich_{uuid.uuid4().hex}"
    admin = create_engine(url, future=True)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, future=True, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(role: str) -> User:
    return User(
        id=uuid.uuid4(), email=f"{role.lower()}-{uuid.uuid4().hex[:6]}@enrich.test", password_hash="x",
        display_name=role, role=role, lecturer_id=None, is_active=True, version=1, auth_version=1,
        created_at=NOW, updated_at=NOW,
    )


@pytest.fixture
def as_role(db_session: Session):
    def _as(role: str) -> User:
        user = _user(role)
        db_session.add(user)
        db_session.commit()
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _as


def _paper(db: Session, imp: ScopusImport, row_number: int, eid: str, doi: str | None, ids: str, names: str) -> None:
    pub = Publication(
        id=uuid.uuid4(), eid=eid, doi=doi, title=f"Title {eid}", title_normalized=f"title {eid}".casefold(),
        source_title="Journal", year=2024, volume=None, issue=None, art_no=None, page_start=None, page_end=None,
        cited_by_count=0, document_type="Article", publication_stage="Final", open_access_status=None,
        version=1, created_at=NOW, updated_at=NOW,
    )
    payload = {"EID": eid, "DOI": doi or "", "Author(s) ID": ids, "Author full names": names}
    raw = RawScopusRecord(
        id=uuid.uuid4(), import_id=imp.id, row_number=row_number, row_hash=f"{row_number:064d}",
        eid_raw=eid, doi_raw=doi, raw_payload=payload, validation_status="VALID", created_at=NOW,
    )
    db.add_all([pub, raw])
    db.flush()
    db.add(PublicationRawSource(publication_id=pub.id, raw_record_id=raw.id))
    for order, sid in enumerate([x.strip() for x in ids.split(";") if x.strip()], start=1):
        author = db.query(ScopusAuthor).filter_by(scopus_id=sid).one_or_none() or ScopusAuthor(
            scopus_id=sid, preferred_name=f"Author {sid}")
        db.add(author)
        db.flush()
        db.add(PublicationAuthor(publication_id=pub.id, scopus_author_id=author.id, author_order=order))


@pytest.fixture
def one_publication(db_session: Session) -> None:
    imp = ScopusImport(
        id=uuid.uuid4(), file_name="new.csv", file_sha256="c" * 64, total_records=1, valid_records=1,
        invalid_records=0, status="APPLIED", version=1, created_at=NOW, updated_at=NOW,
    )
    db_session.add(imp)
    db_session.flush()
    _paper(db_session, imp, 1, "E1", "10.1/enrich-me", "111111", "Alpha, Ann (111111)")
    db_session.commit()


@pytest.fixture
def online_cache_dir(tmp_path, monkeypatch) -> Path:
    directory = tmp_path / "online_cache"
    monkeypatch.setattr(settings, "affiliation_online_cache_dir", str(directory), raising=False)
    return directory


def _mock_empty_handler(request: httpx.Request) -> httpx.Response:
    """Every provider reports 'nothing found' — exercises the plumbing without
    depending on real network state."""
    if request.url.host == "api.openalex.org":
        return httpx.Response(200, json={"results": []})
    if request.url.host == "api.crossref.org":
        return httpx.Response(404, json={})
    if request.url.host == "pub.orcid.org":
        return httpx.Response(200, json={"external-identifier": []})
    raise AssertionError(f"unexpected host {request.url.host}")


@pytest.fixture
def mocked_http(monkeypatch) -> None:
    """Replace the module-level httpx client construction with a mock transport."""

    real_async_client = httpx.AsyncClient

    def _mock_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(_mock_empty_handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(affiliation_online_fetch.httpx, "AsyncClient", _mock_client)


# --------------------------------------------------------------------------- RBAC
@pytest.mark.parametrize("role", ["LECTURER", "REVIEWER"])
def test_only_admin_can_trigger_or_poll_enrichment(client, as_role, role, one_publication, online_cache_dir) -> None:
    as_role(role)
    assert client.post("/api/v1/affiliations/enrichment/online").status_code == 403
    assert client.get(f"/api/v1/affiliations/enrichment/online/{uuid.uuid4()}").status_code == 403
    assert client.post(f"/api/v1/affiliations/enrichment/online/{uuid.uuid4()}/cancel").status_code == 403


def test_anonymous_cannot_trigger_enrichment(client) -> None:
    assert client.post("/api/v1/affiliations/enrichment/online").status_code == 401


# --------------------------------------------------------------------------- guards
def test_refuses_when_online_cache_not_configured(client, as_role, one_publication, monkeypatch) -> None:
    monkeypatch.setattr(settings, "affiliation_online_cache_dir", None, raising=False)
    as_role("ADMIN")
    resp = client.post("/api/v1/affiliations/enrichment/online")
    assert resp.status_code == 409
    assert resp.json()["code"] == "ONLINE_CACHE_NOT_CONFIGURED"


def test_refuses_when_no_publications_exist(client, as_role, online_cache_dir) -> None:
    as_role("ADMIN")
    resp = client.post("/api/v1/affiliations/enrichment/online")
    assert resp.status_code == 409
    assert resp.json()["code"] == "NO_PUBLICATIONS"


def test_refuses_a_second_concurrent_run(client, as_role, db_session, one_publication, online_cache_dir) -> None:
    admin = as_role("ADMIN")
    job = enrichment.start_job(db_session, admin)
    assert job.status == "RECEIVED"
    resp = client.post("/api/v1/affiliations/enrichment/online")
    assert resp.status_code == 409
    assert resp.json()["code"] == "ENRICHMENT_ALREADY_RUNNING"


def test_truly_concurrent_start_job_calls_never_both_succeed(
    db_session, as_role, one_publication, online_cache_dir
) -> None:
    """Two real, independent sessions calling start_job at almost the same
    instant must be serialized by the advisory lock: exactly one job is
    created, never two (a plain SELECT-then-INSERT check has a TOCTOU race
    here — this is what pg_try_advisory_xact_lock in start_job closes)."""

    import threading

    import sqlalchemy.orm as orm_module

    admin = as_role("ADMIN")
    bind = db_session.get_bind()
    factory = orm_module.sessionmaker(autocommit=False, autoflush=False, bind=bind, expire_on_commit=False)

    results: list[object] = []
    barrier = threading.Barrier(2)

    def attempt() -> None:
        session = factory()
        try:
            barrier.wait(timeout=5)
            job = enrichment.start_job(session, admin)
            results.append(job)
        except enrichment.EnrichmentAlreadyRunning as exc:
            results.append(exc)
        finally:
            session.close()

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    successes = [r for r in results if isinstance(r, enrichment.AffiliationEnrichmentJob)]
    refusals = [r for r in results if isinstance(r, enrichment.EnrichmentAlreadyRunning)]
    assert len(successes) == 1, f"expected exactly one job created, got {len(successes)}"
    assert len(refusals) == 1

    db_session.expire_all()
    count = (
        db_session.query(enrichment.AffiliationEnrichmentJob)
        .filter(enrichment.AffiliationEnrichmentJob.status.in_(["RECEIVED", "RUNNING"]))
        .count()
    )
    assert count == 1


def test_poll_unknown_job_id_is_404(client, as_role) -> None:
    as_role("ADMIN")
    assert client.get(f"/api/v1/affiliations/enrichment/online/{uuid.uuid4()}").status_code == 404


# --------------------------------------------------------------------------- trigger (background task scheduling)
def test_trigger_creates_a_received_job_and_schedules_processing(
    client, as_role, one_publication, online_cache_dir, monkeypatch
) -> None:
    """The HTTP layer's job: create the RECEIVED row and hand off to
    BackgroundTasks. Actual processing (``process_enrichment_job`` opening its
    own session via ``get_session_factory()``) is exercised separately below,
    directly against the test schema — matching how ``test_scopus_import_api``
    stubs ``process_import_job`` at the API layer for the same reason: a
    background task's own session does not see a test's isolated schema."""

    import app.api.v1.endpoints.affiliations as affiliations_endpoint

    scheduled: list[uuid.UUID] = []

    def capture_and_release_lease(job_id: uuid.UUID) -> None:
        scheduled.append(job_id)
        enrichment._release_pending_worker_lease(job_id)

    monkeypatch.setattr(
        affiliations_endpoint.enrichment, "process_enrichment_job", capture_and_release_lease
    )
    as_role("ADMIN")
    resp = client.post("/api/v1/affiliations/enrichment/online")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "RECEIVED"
    assert body["total_dois"] == 1
    assert scheduled == [uuid.UUID(body["id"])]


# --------------------------------------------------------------------------- processing (mocked HTTP, same schema)
def test_process_enrichment_job_completes_and_writes_a_readable_bundle(
    db_session, as_role, one_publication, online_cache_dir, mocked_http, monkeypatch
) -> None:
    """Runs ``process_enrichment_job`` directly against the test's own
    isolated-schema session factory, proving the full fetch -> write -> mark
    COMPLETED path end-to-end without the BackgroundTasks/schema mismatch."""

    import sqlalchemy.orm as orm_module

    admin = as_role("ADMIN")
    job = enrichment.start_job(db_session, admin)

    fake_factory = orm_module.sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind(), expire_on_commit=False
    )
    monkeypatch.setattr(enrichment, "get_session_factory", lambda: fake_factory)

    enrichment.process_enrichment_job(job.id)

    db_session.expire_all()
    refreshed = enrichment.get_job(db_session, job.id)
    assert refreshed.status == "COMPLETED"
    assert refreshed.total_dois == 1
    assert refreshed.processed_dois == 1
    assert refreshed.openalex_found == 0  # the mock reports nothing found
    assert refreshed.bundle_dir is not None
    bundle = Path(refreshed.bundle_dir)
    assert bundle.is_dir()
    assert (bundle / "openalex_works.jsonl").is_file()
    assert (bundle / "crossref_works.jsonl").is_file()
    assert (bundle / "orcid_external_ids.json").is_file()


def test_cancel_before_processing_marks_cancelled_and_is_idempotent(
    client, as_role, db_session, one_publication, online_cache_dir
) -> None:
    admin = as_role("ADMIN")
    job = enrichment.start_job(db_session, admin)
    resp = client.post(f"/api/v1/affiliations/enrichment/online/{job.id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"
    # cancelling an already-cancelled job is a no-op, not an error
    resp2 = client.post(f"/api/v1/affiliations/enrichment/online/{job.id}/cancel")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "CANCELLED"


def test_cancel_unknown_job_is_404(client, as_role) -> None:
    as_role("ADMIN")
    assert client.post(f"/api/v1/affiliations/enrichment/online/{uuid.uuid4()}/cancel").status_code == 404


def test_other_admin_cannot_resolve_an_incomplete_jobs_bundle_for_preview(
    client, as_role, db_session, one_publication, online_cache_dir
) -> None:
    admin = as_role("ADMIN")
    job = enrichment.start_job(db_session, admin)  # still RECEIVED, never processed
    resp = client.post("/api/v1/affiliations/preview", params={"job_id": str(job.id)})
    assert resp.status_code == 404
    assert resp.json()["code"] == "ENRICHMENT_JOB_NOT_READY"


def test_preview_by_job_id_reads_that_jobs_bundle_not_the_offline_one(
    client, as_role, db_session, one_publication, online_cache_dir, mocked_http, monkeypatch
) -> None:
    import sqlalchemy.orm as orm_module

    # point the offline bundle somewhere that does NOT exist, to prove job_id
    # preview does not silently fall back to it
    monkeypatch.setattr(settings, "affiliation_source_dir", None, raising=False)
    admin = as_role("ADMIN")
    job = enrichment.start_job(db_session, admin)
    fake_factory = orm_module.sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind(), expire_on_commit=False
    )
    monkeypatch.setattr(enrichment, "get_session_factory", lambda: fake_factory)
    enrichment.process_enrichment_job(job.id)
    db_session.expire_all()

    resp = client.post("/api/v1/affiliations/preview", params={"job_id": str(job.id)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"]["configured"] is True
    assert body["source"]["ready"] is True


# --------------------------------------------------------------------------- latest job lookup (NO-JSON closure)
def test_latest_returns_null_when_no_job_exists(client, as_role) -> None:
    as_role("ADMIN")
    resp = client.get("/api/v1/affiliations/enrichment/online/latest")
    assert resp.status_code == 200
    assert resp.json() is None


def test_latest_finds_the_job_after_a_simulated_page_reload(
    client, as_role, db_session, one_publication, online_cache_dir
) -> None:
    """Simulates exactly the reload/tab-switch gap: nothing on the client
    remembers the job id, so the UI must look it up purely from what the
    trigger call wrote to the database."""

    admin = as_role("ADMIN")
    created = client.post("/api/v1/affiliations/enrichment/online")
    assert created.status_code == 202, created.text
    job_id = created.json()["id"]

    latest = client.get("/api/v1/affiliations/enrichment/online/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == job_id


def test_latest_is_most_recently_created_not_most_recently_updated(
    client, as_role, db_session, one_publication, online_cache_dir
) -> None:
    admin = as_role("ADMIN")
    first = enrichment.start_job(db_session, admin)
    enrichment.cancel_job(db_session, first.id, admin)  # updated_at now newer than its created_at
    db_session.execute(
        text("select pg_sleep(0.05)")
    )  # ensure strictly later created_at for the second job
    second_dois = enrichment._dois_to_enrich(db_session)
    assert second_dois  # sanity: fixture still has the DOI
    # cancel_job left no ACTIVE job, so starting a second one is allowed
    second = enrichment.start_job(db_session, admin)

    resp = client.get("/api/v1/affiliations/enrichment/online/latest")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(second.id)


def test_latest_is_admin_only(client, as_role) -> None:
    as_role("LECTURER")
    assert client.get("/api/v1/affiliations/enrichment/online/latest").status_code == 403


# --------------------------------------------------------------------------- startup recovery after an interrupted job
def test_recover_marks_active_jobs_failed_with_a_clear_reason(db_session, as_role, one_publication, online_cache_dir, monkeypatch) -> None:
    """Simulates a backend restart while a job was RECEIVED/RUNNING: no
    in-process task survives, so the job must never be silently resumed —
    it is marked FAILED with a reason the ADMIN UI can show, not left
    spinning forever."""

    import sqlalchemy.orm as orm_module

    admin = as_role("ADMIN")
    job = enrichment.start_job(db_session, admin)
    assert job.status == "RECEIVED"

    fake_factory = orm_module.sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind(), expire_on_commit=False
    )
    monkeypatch.setattr(enrichment, "get_session_factory", lambda: fake_factory)

    recovered_count = enrichment.recover_interrupted_enrichment_jobs()
    assert recovered_count == 1

    db_session.expire_all()
    reloaded = enrichment.get_job(db_session, job.id)
    assert reloaded.status == "FAILED"
    assert reloaded.error_summary["code"] == "ENRICHMENT_INTERRUPTED"


def test_recover_does_not_fail_a_job_with_a_live_worker_lease(
    db_session, as_role, one_publication, online_cache_dir, monkeypatch
) -> None:
    """A different backend process must not mark this process's live job failed."""

    import sqlalchemy.orm as orm_module

    admin = as_role("ADMIN")
    job = enrichment.start_job(db_session, admin, reserve_worker_lease=True)
    fake_factory = orm_module.sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind(), expire_on_commit=False
    )
    monkeypatch.setattr(enrichment, "get_session_factory", lambda: fake_factory)

    try:
        assert enrichment.recover_interrupted_enrichment_jobs() == 0
        db_session.expire_all()
        assert enrichment.get_job(db_session, job.id).status == "RECEIVED"
    finally:
        enrichment._release_pending_worker_lease(job.id)

    assert enrichment.recover_interrupted_enrichment_jobs() == 1
    db_session.expire_all()
    reloaded = enrichment.get_job(db_session, job.id)
    assert reloaded.status == "FAILED"
    assert reloaded.error_summary["code"] == "ENRICHMENT_INTERRUPTED"


def test_recover_leaves_completed_and_failed_jobs_untouched(db_session, as_role, one_publication, online_cache_dir, monkeypatch) -> None:
    import sqlalchemy.orm as orm_module

    admin = as_role("ADMIN")
    job = enrichment.start_job(db_session, admin)
    job.status = "COMPLETED"
    db_session.commit()

    fake_factory = orm_module.sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind(), expire_on_commit=False
    )
    monkeypatch.setattr(enrichment, "get_session_factory", lambda: fake_factory)

    recovered_count = enrichment.recover_interrupted_enrichment_jobs()
    assert recovered_count == 0

    db_session.expire_all()
    reloaded = enrichment.get_job(db_session, job.id)
    assert reloaded.status == "COMPLETED"


def test_recover_with_no_active_jobs_is_a_no_op(db_session, monkeypatch) -> None:
    import sqlalchemy.orm as orm_module

    fake_factory = orm_module.sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind(), expire_on_commit=False
    )
    monkeypatch.setattr(enrichment, "get_session_factory", lambda: fake_factory)

    assert enrichment.recover_interrupted_enrichment_jobs() == 0
