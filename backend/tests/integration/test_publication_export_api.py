"""Integration contract tests for the Completion-1 A4 publication export API."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.models.governance import AuditEvent, User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor

EXPORT_URL = "/api/v1/publications/export"
LIST_URL = "/api/v1/publications"


# ---------------------------------------------------------------------------
# Session / client / auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for A4 integration tests")
    database = make_url(url).database
    if database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("A4 tests must never target an acceptance database")

    schema = f"test_c1_a4_pub_export_{uuid.uuid4().hex}"
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
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
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
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def authenticate(db_session: Session):
    def _auth(role: str) -> User:
        u = User(
            id=uuid.uuid4(),
            email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@a4.test",
            password_hash="not-used",
            display_name=f"A4 {role}",
            role=role,
            lecturer_id=None,
            is_active=True,
            version=1,
            auth_version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        # Persist ADMIN/REVIEWER users so AuditEvent.actor_user_id FK is
        # satisfied when the endpoint commits. LECTURER users are rejected at
        # the role-check before any DB write, so we skip the DB insert
        # (the users table CHECK enforces lecturer_id IS NOT NULL for LECTURER).
        if role in ("ADMIN", "REVIEWER"):
            db_session.add(u)
            db_session.flush()
        app.dependency_overrides[get_current_user] = lambda: u
        return u
    return _auth


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(UTC)


def _pub(
    eid: str,
    title: str,
    *,
    year: int | None = None,
    doi: str | None = None,
    source_title: str | None = None,
    cited_by_count: int | None = None,
    document_type: str | None = "Article",
    publication_stage: str | None = None,
    open_access_status: str | None = None,
) -> Publication:
    now = _now()
    return Publication(
        id=uuid.uuid4(),
        eid=eid,
        doi=doi,
        title=title,
        title_normalized=title.casefold(),
        source_title=source_title,
        year=year,
        volume=None,
        issue=None,
        art_no=None,
        page_start=None,
        page_end=None,
        cited_by_count=cited_by_count,
        document_type=document_type,
        publication_stage=publication_stage,
        open_access_status=open_access_status,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _author(scopus_id: str, preferred_name: str) -> ScopusAuthor:
    now = _now()
    return ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id=scopus_id,
        preferred_name=preferred_name,
        created_at=now,
        updated_at=now,
    )


def _lecturer(full_name: str, *, staff_code: str | None = None) -> Lecturer:
    now = _now()
    return Lecturer(
        id=uuid.uuid4(),
        staff_code=staff_code,
        full_name=full_name,
        full_name_normalized=full_name.casefold(),
        email=None,
        academic_rank=None,
        academic_degree=None,
        position=None,
        department=None,
        faculty=None,
        repository_profile_url=None,
        repository_profile_id=None,
        orcid=None,
        is_active=True,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _link(pub: Publication, author: ScopusAuthor, order: int) -> PublicationAuthor:
    return PublicationAuthor(
        id=uuid.uuid4(),
        publication_id=pub.id,
        scopus_author_id=author.id,
        author_order=order,
        created_at=_now(),
    )


def _identity(
    lecturer: Lecturer,
    author: ScopusAuthor,
    *,
    status: str = "APPROVED",
) -> LecturerScopusIdentity:
    now = _now()
    return LecturerScopusIdentity(
        id=uuid.uuid4(),
        lecturer_id=lecturer.id,
        scopus_author_id=author.id,
        status=status,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Helper: seed a minimal dataset
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded(db_session: Session) -> dict:
    p1 = _pub("2-s2.0-EXP001", "Export alpha study", year=2022, doi="10.1/a", cited_by_count=5)
    p2 = _pub("2-s2.0-EXP002", "Export beta survey", year=2020, cited_by_count=0)
    p3 = _pub("2-s2.0-EXP003", "Export null year", year=None, cited_by_count=None)
    p4 = _pub("2-s2.0-EXP004", "Export conference paper",
              year=2021, document_type="Conference Paper",
              publication_stage="Final", open_access_status="Gold")

    a1 = _author("57200000001", "Alpha Researcher")
    a2 = _author("57200000002", "Beta Researcher")

    lec = _lecturer("ICTU Lecturer One", staff_code="LC001")

    db_session.add_all([p1, p2, p3, p4, a1, a2, lec])
    db_session.flush()

    db_session.add_all([
        _link(p1, a1, 1),
        _link(p1, a2, 2),
        _link(p2, a1, 1),
        _identity(lec, a1, status="APPROVED"),
    ])
    db_session.commit()

    return {"p1": p1, "p2": p2, "p3": p3, "p4": p4, "a1": a1, "a2": a2, "lec": lec}


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

def test_export_requires_authentication(client: TestClient) -> None:
    assert client.get(EXPORT_URL).status_code == 401


def test_export_rejects_lecturer(client: TestClient, authenticate) -> None:
    authenticate("LECTURER")
    assert client.get(EXPORT_URL).status_code == 403


def test_export_rejects_reviewer(client: TestClient, authenticate) -> None:
    authenticate("REVIEWER")
    assert client.get(EXPORT_URL).status_code == 403


def test_export_allows_admin(client: TestClient, authenticate, seeded) -> None:
    authenticate("ADMIN")
    r = client.get(EXPORT_URL)
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Static /export route does not match /{eid}
# ---------------------------------------------------------------------------

def test_export_route_not_consumed_as_eid(
    client: TestClient, authenticate, db_session: Session
) -> None:
    authenticate("REVIEWER")
    r = client.get(f"{LIST_URL}/export")
    # Must be 403 (REVIEWER blocked from export) not 404 (mis-routed as EID)
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# HTTP contract
# ---------------------------------------------------------------------------

def test_export_content_type(client: TestClient, authenticate, seeded) -> None:
    authenticate("ADMIN")
    r = client.get(EXPORT_URL)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct


def test_export_content_disposition(client: TestClient, authenticate, seeded) -> None:
    authenticate("ADMIN")
    r = client.get(EXPORT_URL)
    assert r.status_code == 200
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "ictu_publications_" in cd
    assert cd.endswith('.json"') or cd.endswith(".json")


def test_export_envelope_shape(client: TestClient, authenticate, seeded) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL).json()
    assert "dataset" in body
    assert "publications" in body
    ds = body["dataset"]
    assert ds["schema_version"] == "1.0"
    assert ds["name"] == "ICTU Publication Export"
    assert ds["source"] == "SCOPUS_ICTU_SYSTEM_EXPORT"
    assert "export_id" in ds
    assert "exported_at" in ds
    assert isinstance(ds["record_count"], int)
    assert ds["record_count"] == len(body["publications"])


def test_export_no_filters_returns_all(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL).json()
    assert len(body["publications"]) == 4


# ---------------------------------------------------------------------------
# Filter semantics
# ---------------------------------------------------------------------------

def test_export_filter_year(client: TestClient, authenticate, seeded) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"year": 2022}).json()
    assert all(p["year"] == 2022 for p in body["publications"])
    assert len(body["publications"]) == 1


def test_export_filter_document_type(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"document_type": "Conference Paper"}).json()
    assert all(p["document_type"] == "Conference Paper" for p in body["publications"])
    assert len(body["publications"]) == 1


def test_export_filter_publication_stage(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"publication_stage": "Final"}).json()
    assert len(body["publications"]) == 1
    assert body["publications"][0]["publication_stage"] == "Final"


def test_export_filter_open_access_status(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"open_access_status": "Gold"}).json()
    assert len(body["publications"]) == 1


def test_export_filter_combined(client: TestClient, authenticate, seeded) -> None:
    authenticate("ADMIN")
    body = client.get(
        EXPORT_URL,
        params={"document_type": "Conference Paper", "year": 2021},
    ).json()
    assert len(body["publications"]) == 1


def test_export_filter_q_literal_substring(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"q": "alpha"}).json()
    assert len(body["publications"]) == 1
    assert "alpha" in body["publications"][0]["title"].lower()


@pytest.mark.parametrize("raw_q", ["%%", "__", "\\\\"])
def test_export_q_like_metacharacters_literal(
    client: TestClient, authenticate, seeded, raw_q: str
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"q": raw_q}).json()
    # Seeded titles contain no literal %, _, \
    assert body["publications"] == []


def test_export_q_in_filters_applied(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"q": "alpha"}).json()
    assert body["dataset"]["filters_applied"].get("q") == "alpha"


def test_export_empty_filters_applied_when_no_filters(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL).json()
    assert body["dataset"]["filters_applied"] == {}


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_export_publication_order_deterministic(
    client: TestClient, authenticate, db_session: Session
) -> None:
    db_session.add_all([
        _pub("2-s2.0-ORD1", "Order oldest", year=2010),
        _pub("2-s2.0-ORD3", "Order newest", year=2024),
        _pub("2-s2.0-ORD2", "Order no year", year=None),
    ])
    db_session.commit()
    authenticate("ADMIN")

    first = client.get(EXPORT_URL, params={"q": "Order"}).json()
    second = client.get(EXPORT_URL, params={"q": "Order"}).json()
    eids = [p["eid"] for p in first["publications"]]
    assert eids == ["2-s2.0-ORD3", "2-s2.0-ORD1", "2-s2.0-ORD2"]
    assert eids == [p["eid"] for p in second["publications"]]


def test_export_authors_ordered(client: TestClient, authenticate, seeded) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"q": "alpha"}).json()
    pub = body["publications"][0]
    orders = [a["author_order"] for a in pub["authors"]]
    assert orders == sorted(orders)


# ---------------------------------------------------------------------------
# Null / zero preservation
# ---------------------------------------------------------------------------

def test_export_null_year_preserved(client: TestClient, authenticate, seeded) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL).json()
    by_eid = {p["eid"]: p for p in body["publications"]}
    assert by_eid["2-s2.0-EXP003"]["year"] is None


def test_export_null_citation_preserved(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL).json()
    by_eid = {p["eid"]: p for p in body["publications"]}
    assert by_eid["2-s2.0-EXP003"]["cited_by_count"] is None


def test_export_zero_citation_not_null(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL).json()
    by_eid = {p["eid"]: p for p in body["publications"]}
    assert by_eid["2-s2.0-EXP002"]["cited_by_count"] == 0


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

def test_export_authors_included(client: TestClient, authenticate, seeded) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"q": "alpha"}).json()
    pub = body["publications"][0]
    assert len(pub["authors"]) == 2
    scopus_ids = {a["scopus_id"] for a in pub["authors"]}
    assert "57200000001" in scopus_ids
    assert "57200000002" in scopus_ids


def test_export_approved_lecturer_links_included(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL, params={"q": "alpha"}).json()
    pub = body["publications"][0]
    assert len(pub["approved_lecturer_links"]) == 1
    assert pub["approved_lecturer_links"][0]["full_name"] == "ICTU Lecturer One"


def test_export_rejected_lecturer_link_excluded(
    client: TestClient, authenticate, db_session: Session
) -> None:
    p = _pub("2-s2.0-REJ001", "Rejected link pub", year=2023)
    a = _author("57299999001", "Reject Author")
    lec = _lecturer("Reject Lecturer")
    db_session.add_all([p, a, lec])
    db_session.flush()
    db_session.add(_link(p, a, 1))
    db_session.add(_identity(lec, a, status="REJECTED"))
    db_session.commit()
    authenticate("ADMIN")

    body = client.get(EXPORT_URL, params={"q": "Rejected link"}).json()
    assert len(body["publications"]) == 1
    assert body["publications"][0]["approved_lecturer_links"] == []


def test_export_candidate_lecturer_link_excluded(
    client: TestClient, authenticate, db_session: Session
) -> None:
    p = _pub("2-s2.0-CAND001", "Candidate link pub", year=2023)
    a = _author("57299999002", "Cand Author")
    lec = _lecturer("Cand Lecturer")
    db_session.add_all([p, a, lec])
    db_session.flush()
    db_session.add(_link(p, a, 1))
    db_session.add(_identity(lec, a, status="CANDIDATE"))
    db_session.commit()
    authenticate("ADMIN")

    body = client.get(EXPORT_URL, params={"q": "Candidate link"}).json()
    assert body["publications"][0]["approved_lecturer_links"] == []


def test_export_pub_no_authors_has_empty_lists(
    client: TestClient, authenticate, db_session: Session
) -> None:
    p = _pub("2-s2.0-SOLO001", "Solo pub no authors", year=2023)
    db_session.add(p)
    db_session.commit()
    authenticate("ADMIN")

    body = client.get(EXPORT_URL, params={"q": "Solo pub"}).json()
    pub = body["publications"][0]
    assert pub["authors"] == []
    assert pub["approved_lecturer_links"] == []


# ---------------------------------------------------------------------------
# No internal UUID / security / raw leakage
# ---------------------------------------------------------------------------

def test_export_no_internal_uuid_fields(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL).json()
    forbidden_keys = {
        "id", "publication_id", "scopus_author_id", "lecturer_id",
        "raw_record_id", "import_id",
    }
    for pub in body["publications"]:
        assert not (forbidden_keys & pub.keys()), pub.keys()
        for a in pub["authors"]:
            assert not (forbidden_keys & a.keys()), a.keys()
        for link in pub["approved_lecturer_links"]:
            assert not (forbidden_keys & link.keys()), link.keys()


def test_export_no_raw_provenance_fields(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    serialized = client.get(EXPORT_URL).text
    for forbidden in ("file_sha256", "row_number", "file_name", "raw_record_id"):
        assert forbidden not in serialized, forbidden


def test_export_no_security_fields(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    serialized = client.get(EXPORT_URL).text
    for forbidden in ("password_hash", "auth_version"):
        assert forbidden not in serialized, forbidden


def test_export_no_title_normalized(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    serialized = client.get(EXPORT_URL).text
    assert "title_normalized" not in serialized


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def test_export_audit_written_on_success(
    client: TestClient, authenticate, db_session: Session, seeded
) -> None:
    authenticate("ADMIN")
    r = client.get(EXPORT_URL)
    assert r.status_code == 200

    events = db_session.query(AuditEvent).filter(
        AuditEvent.action == "PUBLICATION_DATASET_EXPORTED"
    ).all()
    assert len(events) == 1
    ev = events[0]
    assert ev.entity_type == "publication_export"
    assert ev.actor_type == "USER"
    assert ev.actor_user_id is not None


def test_export_audit_entity_id_equals_dataset_export_id(
    client: TestClient, authenticate, db_session: Session, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL).json()
    export_id = uuid.UUID(body["dataset"]["export_id"])

    ev = db_session.query(AuditEvent).filter(
        AuditEvent.action == "PUBLICATION_DATASET_EXPORTED"
    ).one()
    assert ev.entity_id == export_id


def test_export_audit_record_count_matches(
    client: TestClient, authenticate, db_session: Session, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(EXPORT_URL).json()

    ev = db_session.query(AuditEvent).filter(
        AuditEvent.action == "PUBLICATION_DATASET_EXPORTED"
    ).one()
    assert ev.event_metadata["record_count"] == len(body["publications"])


def test_export_exactly_one_audit_per_call(
    client: TestClient, authenticate, db_session: Session, seeded
) -> None:
    authenticate("ADMIN")
    client.get(EXPORT_URL)
    client.get(EXPORT_URL)

    events = db_session.query(AuditEvent).filter(
        AuditEvent.action == "PUBLICATION_DATASET_EXPORTED"
    ).all()
    assert len(events) == 2


def test_export_audit_filters_applied_recorded(
    client: TestClient, authenticate, db_session: Session, seeded
) -> None:
    authenticate("ADMIN")
    client.get(EXPORT_URL, params={"year": 2022, "document_type": "Article"})

    ev = db_session.query(AuditEvent).filter(
        AuditEvent.action == "PUBLICATION_DATASET_EXPORTED"
    ).one()
    fa = ev.event_metadata["filters_applied"]
    assert fa.get("year") == 2022
    assert fa.get("document_type") == "Article"


# ---------------------------------------------------------------------------
# DB failure behavior
# ---------------------------------------------------------------------------

def test_export_query_failure_returns_503(
    client: TestClient, authenticate, db_session: Session
) -> None:
    authenticate("ADMIN")

    import app.api.v1.endpoints.publications as pub_ep
    from app.services.publication_export import export_publications as real_fn

    def _boom(*_args, **_kwargs):
        from sqlalchemy.exc import OperationalError
        raise OperationalError("select 1", {}, Exception("db down"))

    pub_ep.export_publications = _boom
    try:
        r = client.get(EXPORT_URL)
    finally:
        pub_ep.export_publications = real_fn

    assert r.status_code == 503
    assert r.json()["code"] == "DATABASE_UNAVAILABLE"

    events = db_session.query(AuditEvent).filter(
        AuditEvent.action == "PUBLICATION_DATASET_EXPORTED"
    ).all()
    assert events == []


def test_export_audit_commit_failure_returns_503(
    client: TestClient, authenticate, db_session: Session, seeded
) -> None:
    authenticate("ADMIN")

    import app.api.v1.endpoints.publications as pub_ep

    original_commit = db_session.commit

    call_count = {"n": 0}

    def _fail_commit():
        call_count["n"] += 1
        from sqlalchemy.exc import OperationalError
        raise OperationalError("commit", {}, Exception("disk full"))

    db_session.commit = _fail_commit
    try:
        r = client.get(EXPORT_URL)
    finally:
        db_session.commit = original_commit

    assert r.status_code == 503
    assert r.json()["code"] == "DATABASE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Regression: existing A1/A2 endpoints still work
# ---------------------------------------------------------------------------

def test_list_publications_still_works(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("REVIEWER")
    r = client.get(LIST_URL)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


def test_get_publication_by_eid_still_works(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("REVIEWER")
    r = client.get(f"{LIST_URL}/2-s2.0-EXP001")
    assert r.status_code == 200
    body = r.json()
    assert body["eid"] == "2-s2.0-EXP001"


def test_get_publication_unknown_eid_404(
    client: TestClient, authenticate
) -> None:
    authenticate("REVIEWER")
    r = client.get(f"{LIST_URL}/2-s2.0-DOES-NOT-EXIST")
    assert r.status_code == 404
    assert r.json()["code"] == "PUBLICATION_NOT_FOUND"


def test_reviewer_can_browse_but_not_export(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("REVIEWER")
    assert client.get(LIST_URL).status_code == 200
    assert client.get(EXPORT_URL).status_code == 403
