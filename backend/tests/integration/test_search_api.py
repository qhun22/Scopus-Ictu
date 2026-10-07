"""Integration contract tests for the Completion-1 A3 global search API."""

from __future__ import annotations

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
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, ScopusAuthor

SEARCH_URL = "/api/v1/search"


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a disposable schema from the explicit isolated test URL."""

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for A3 integration tests")
    database = make_url(url).database
    if database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("A3 tests must never target an acceptance database")

    schema = f"test_c1_a3_search_{uuid.uuid4().hex}"
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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def authenticate():
    def _authenticate(role: str) -> None:
        current_user = User(
            id=uuid.uuid4(),
            email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@a3.test",
            password_hash="not-used",
            display_name=f"A3 {role}",
            role=role,
            lecturer_id=None,
            is_active=True,
            version=1,
            auth_version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        app.dependency_overrides[get_current_user] = lambda: current_user

    return _authenticate


def _lecturer(
    full_name: str,
    *,
    staff_code: str | None = None,
    department: str | None = None,
    faculty: str | None = None,
    orcid: str | None = None,
    is_active: bool = True,
) -> Lecturer:
    now = datetime.now(UTC)
    return Lecturer(
        id=uuid.uuid4(),
        staff_code=staff_code,
        full_name=full_name,
        full_name_normalized=full_name.casefold(),
        email=None,
        academic_rank=None,
        academic_degree=None,
        position=None,
        department=department,
        faculty=faculty,
        repository_profile_url=None,
        repository_profile_id=None,
        orcid=orcid,
        is_active=is_active,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _publication(
    eid: str,
    title: str,
    *,
    year: int | None = None,
    doi: str | None = None,
    source_title: str | None = None,
    cited_by_count: int | None = None,
    document_type: str | None = "Article",
) -> Publication:
    now = datetime.now(UTC)
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
        publication_stage=None,
        open_access_status=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _scopus_author(scopus_id: str, preferred_name: str) -> ScopusAuthor:
    now = datetime.now(UTC)
    return ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id=scopus_id,
        preferred_name=preferred_name,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def seeded(db_session: Session) -> None:
    db_session.add_all(
        [
            _lecturer(
                "Nguyen Van Alpha",
                staff_code="GV001",
                department="Khoa học máy tính",
                faculty="Công nghệ thông tin",
                orcid="0000-0001-0000-0001",
            ),
            _lecturer(
                "Tran Thi Beta",
                staff_code="GV002",
                department="Hệ thống thông tin",
            ),
            _lecturer("Le Van Inactive", staff_code="GV003", is_active=False),
            _publication(
                "2-s2.0-ALPHA1",
                "Alpha study on retrieval",
                year=2021,
                doi="10.1000/alpha",
                source_title="Journal of Alpha",
                cited_by_count=12,
            ),
            _publication(
                "2-s2.0-ALPHA2",
                "Alpha survey follow-up",
                year=None,
                cited_by_count=None,
            ),
            _publication(
                "2-s2.0-ALPHA3",
                "Alpha zero citation record",
                year=2019,
                cited_by_count=0,
            ),
            _scopus_author("57210000001", "Alpha Author"),
            _scopus_author("57210000002", "Beta Author"),
        ]
    )
    db_session.commit()


def test_search_requires_authentication(client: TestClient) -> None:
    assert client.get(SEARCH_URL, params={"q": "alpha"}).status_code == 401


def test_search_rejects_lecturer_role(client: TestClient, authenticate) -> None:
    authenticate("LECTURER")
    assert client.get(SEARCH_URL, params={"q": "alpha"}).status_code == 403


@pytest.mark.parametrize("role", ["ADMIN", "REVIEWER"])
def test_search_allows_reader_roles(
    client: TestClient, authenticate, seeded, role: str
) -> None:
    authenticate(role)
    response = client.get(SEARCH_URL, params={"q": "alpha"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["q"] == "alpha"
    assert body["limit"] == 5
    assert body["lecturers"]
    assert body["publications"]
    assert body["scopus_authors"]


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "   "}, {"q": "a"}])
def test_search_rejects_short_or_blank_query(
    client: TestClient, authenticate, params: dict
) -> None:
    authenticate("ADMIN")
    response = client.get(SEARCH_URL, params=params)

    assert response.status_code == 422, response.text


def test_search_trims_query_before_matching(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    response = client.get(SEARCH_URL, params={"q": "  alpha  "})

    assert response.status_code == 200, response.text
    assert response.json()["q"] == "alpha"


@pytest.mark.parametrize("raw_q", ["%%", "__", "\\\\"])
def test_search_treats_like_metacharacters_literally(
    client: TestClient, authenticate, seeded, raw_q: str
) -> None:
    authenticate("ADMIN")
    response = client.get(SEARCH_URL, params={"q": raw_q})

    assert response.status_code == 200, response.text
    body = response.json()
    # Every seeded row lacks a literal '%', '_', or '\' in its searchable
    # columns, so a correct literal match returns nothing. If the escaping
    # were broken, '%' and '_' would act as wildcards and match everything.
    assert body["lecturers"] == []
    assert body["publications"] == []
    assert body["scopus_authors"] == []


@pytest.mark.parametrize("limit", [1, 5, 20])
def test_search_accepts_valid_limits(
    client: TestClient, authenticate, seeded, limit: int
) -> None:
    authenticate("ADMIN")
    response = client.get(SEARCH_URL, params={"q": "alpha", "limit": limit})

    assert response.status_code == 200, response.text
    assert response.json()["limit"] == limit


@pytest.mark.parametrize("limit", [0, 21])
def test_search_rejects_invalid_limits(
    client: TestClient, authenticate, limit: int
) -> None:
    authenticate("ADMIN")
    response = client.get(SEARCH_URL, params={"q": "alpha", "limit": limit})

    assert response.status_code == 422, response.text


def test_search_caps_each_group_at_limit(
    client: TestClient, authenticate, db_session: Session
) -> None:
    db_session.add_all(
        [_lecturer(f"Cap Lecturer {index}") for index in range(8)]
    )
    db_session.commit()
    authenticate("ADMIN")

    response = client.get(SEARCH_URL, params={"q": "cap", "limit": 5})

    assert response.status_code == 200, response.text
    assert len(response.json()["lecturers"]) == 5


def test_search_ordering_is_deterministic(
    client: TestClient, authenticate, db_session: Session
) -> None:
    db_session.add_all(
        [
            _publication("2-s2.0-DET1", "Deterministic older", year=2005),
            _publication("2-s2.0-DET3", "Deterministic newest", year=2024),
            _publication("2-s2.0-DET2", "Deterministic undated", year=None),
        ]
    )
    db_session.commit()
    authenticate("ADMIN")

    first = client.get(SEARCH_URL, params={"q": "deterministic"}).json()
    second = client.get(SEARCH_URL, params={"q": "deterministic"}).json()

    eids = [item["eid"] for item in first["publications"]]
    assert eids == ["2-s2.0-DET3", "2-s2.0-DET1", "2-s2.0-DET2"]
    assert eids == [item["eid"] for item in second["publications"]]


def test_search_preserves_null_and_zero_citation(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    by_eid = {
        item["eid"]: item
        for item in client.get(SEARCH_URL, params={"q": "alpha", "limit": 20}).json()[
            "publications"
        ]
    }

    assert by_eid["2-s2.0-ALPHA2"]["year"] is None
    assert by_eid["2-s2.0-ALPHA2"]["cited_by_count"] is None
    assert by_eid["2-s2.0-ALPHA3"]["cited_by_count"] == 0


def test_search_excludes_inactive_lecturer(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    names = [
        item["full_name"]
        for item in client.get(SEARCH_URL, params={"q": "inactive"}).json()["lecturers"]
    ]

    assert names == []


def test_search_returns_empty_groups_for_no_match(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    response = client.get(SEARCH_URL, params={"q": "zzz-no-such-term"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["lecturers"] == []
    assert body["publications"] == []
    assert body["scopus_authors"] == []


def test_search_dto_exposes_no_internal_identifiers(
    client: TestClient, authenticate, seeded
) -> None:
    authenticate("ADMIN")
    body = client.get(SEARCH_URL, params={"q": "alpha", "limit": 20}).json()

    forbidden = {"id", "lecturer_id", "publication_id", "author_id", "email"}
    for group in ("lecturers", "publications", "scopus_authors"):
        for item in body[group]:
            assert not (forbidden & item.keys()), item
    # Raw provenance / source-row fields must never appear.
    serialized = client.get(SEARCH_URL, params={"q": "alpha", "limit": 20}).text
    assert "file_sha256" not in serialized
    assert "row_number" not in serialized
    assert "provenance" not in serialized


def test_search_accepts_exactly_255_trimmed_chars(
    client: TestClient, authenticate
) -> None:
    authenticate("ADMIN")
    q = "a" * 255
    response = client.get(SEARCH_URL, params={"q": q})
    assert response.status_code == 200, response.text
    assert response.json()["q"] == q


def test_search_rejects_256_trimmed_chars(
    client: TestClient, authenticate
) -> None:
    authenticate("ADMIN")
    q = "a" * 256
    response = client.get(SEARCH_URL, params={"q": q})
    assert response.status_code == 422, response.text


def test_search_accepts_padded_query_within_trimmed_limit(
    client: TestClient, authenticate
) -> None:
    """Raw q >255 due to surrounding whitespace, but trimmed q is valid."""
    authenticate("ADMIN")
    trimmed = "ab"
    q = " " * 300 + trimmed + " " * 300
    assert len(q) > 255
    response = client.get(SEARCH_URL, params={"q": q})
    assert response.status_code == 200, response.text
    assert response.json()["q"] == trimmed


def test_search_lecturer_order_is_total_with_null_staff_code(
    client: TestClient, authenticate, db_session: Session
) -> None:
    """Lecturers with the same full_name_normalized and NULL staff_code must
    still sort deterministically via the UUID tie-breaker."""
    import uuid as _uuid

    id_a = _uuid.UUID("00000000-0000-0000-0000-000000000001")
    id_b = _uuid.UUID("00000000-0000-0000-0000-000000000002")
    now = datetime.now(UTC)
    for lecturer_id, name in [(id_a, "Tie Lecturer"), (id_b, "Tie Lecturer")]:
        db_session.add(
            Lecturer(
                id=lecturer_id,
                staff_code=None,
                full_name=name,
                full_name_normalized="tie lecturer",
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
        )
    db_session.commit()
    authenticate("ADMIN")

    first = client.get(SEARCH_URL, params={"q": "Tie Lecturer", "limit": 20}).json()
    second = client.get(SEARCH_URL, params={"q": "Tie Lecturer", "limit": 20}).json()

    ids_first = [item.get("staff_code") for item in first["lecturers"]]
    ids_second = [item.get("staff_code") for item in second["lecturers"]]
    assert ids_first == ids_second, "Order must be deterministic across repeated calls"
    assert len(first["lecturers"]) == 2


def test_search_reports_database_unavailable(
    client: TestClient, authenticate, db_session: Session
) -> None:
    authenticate("ADMIN")

    def _boom(*_args, **_kwargs):
        from sqlalchemy.exc import OperationalError

        raise OperationalError("select 1", {}, Exception("db down"))

    import app.api.v1.endpoints.search as search_endpoint

    original = search_endpoint.global_search
    search_endpoint.global_search = _boom
    try:
        response = client.get(SEARCH_URL, params={"q": "alpha"})
    finally:
        search_endpoint.global_search = original

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "DATABASE_UNAVAILABLE"