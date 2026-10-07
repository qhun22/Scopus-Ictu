"""Integration contract tests for the Completion-1 A1 publication read API."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

import app.api.v1.endpoints.publications as publications_endpoint
from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import (
    Publication,
    PublicationAuthor,
    PublicationRawSource,
    ScopusAuthor,
)
from app.models.scopus_raw import RawScopusRecord, ScopusImport


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a disposable schema from the explicit isolated test URL."""

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for A1 integration tests")
    database = make_url(url).database
    if database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("A1 tests must never target an acceptance database")

    schema = f"test_c1_a1_publications_{uuid.uuid4().hex}"
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


def _user(role: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@a1.test",
        password_hash="not-used",
        display_name=f"A1 {role}",
        role=role,
        lecturer_id=None,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def authenticate():
    def _authenticate(role: str) -> None:
        current_user = _user(role)
        app.dependency_overrides[get_current_user] = lambda: current_user

    return _authenticate


def _publication(
    eid: str,
    title: str,
    *,
    year: int | None,
    doi: str | None,
    source_title: str | None,
    cited_by_count: int | None,
    document_type: str | None = "Article",
    publication_stage: str | None = "Final",
    open_access_status: str | None = "Open",
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
        publication_stage=publication_stage,
        open_access_status=open_access_status,
        version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def catalog(db_session: Session) -> dict[str, Publication]:
    publications = {
        "alpha": _publication(
            "EID-2024-A",
            "Alpha Methods",
            year=2024,
            doi="10.1000/alpha",
            source_title="Journal A",
            cited_by_count=5,
        ),
        "beta": _publication(
            "EID-2024-B",
            "Beta Results",
            year=2024,
            doi="10.1000/beta",
            source_title="Journal B",
            cited_by_count=0,
            document_type="Conference Paper",
            publication_stage="Article in Press",
            open_access_status="Closed",
        ),
        "gamma": _publication(
            "EID-2023-G",
            "Gamma Networks",
            year=2023,
            doi="10.1000/gamma",
            source_title="Target Source",
            cited_by_count=2,
        ),
        "delta": _publication(
            "EID-NULL-D",
            "Delta Unknown",
            year=None,
            doi="10.1000/delta",
            source_title="Journal D",
            cited_by_count=None,
        ),
        "epsilon": _publication(
            "EID-2022-E",
            "Epsilon No DOI",
            year=2022,
            doi=None,
            source_title="Journal E",
            cited_by_count=1,
        ),
    }
    db_session.add_all(publications.values())

    approved_author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id="1001",
        preferred_name="Approved One",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    second_approved_author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id="1002",
        preferred_name="Approved Two",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    candidate_author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id="1003",
        preferred_name="Candidate Author",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    rejected_author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id="1004",
        preferred_name="Rejected Author",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add_all(
        [approved_author, second_approved_author, candidate_author, rejected_author]
    )
    db_session.flush()

    db_session.add_all(
        [
            PublicationAuthor(
                id=uuid.uuid4(),
                publication_id=publications["alpha"].id,
                scopus_author_id=approved_author.id,
                author_order=1,
                created_at=datetime.now(UTC),
            ),
            PublicationAuthor(
                id=uuid.uuid4(),
                publication_id=publications["alpha"].id,
                scopus_author_id=candidate_author.id,
                author_order=2,
                created_at=datetime.now(UTC),
            ),
            PublicationAuthor(
                id=uuid.uuid4(),
                publication_id=publications["alpha"].id,
                scopus_author_id=rejected_author.id,
                author_order=3,
                created_at=datetime.now(UTC),
            ),
            PublicationAuthor(
                id=uuid.uuid4(),
                publication_id=publications["alpha"].id,
                scopus_author_id=second_approved_author.id,
                author_order=5,
                created_at=datetime.now(UTC),
            ),
        ]
    )

    lecturers = [
        Lecturer(
            id=uuid.uuid4(),
            staff_code="CB-001",
            full_name="Lecturer One",
            full_name_normalized="lecturer one",
            department="Software Engineering",
            faculty="ICT",
            orcid="0000-0002-1825-0097",
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        Lecturer(
            id=uuid.uuid4(),
            staff_code="CB-002",
            full_name="Lecturer Two",
            full_name_normalized="lecturer two",
            department="Computer Science",
            faculty="ICT",
            orcid=None,
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        Lecturer(
            id=uuid.uuid4(),
            staff_code="CB-003",
            full_name="Lecturer Candidate",
            full_name_normalized="lecturer candidate",
            department=None,
            faculty=None,
            orcid=None,
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        Lecturer(
            id=uuid.uuid4(),
            staff_code="CB-004",
            full_name="Lecturer Rejected",
            full_name_normalized="lecturer rejected",
            department=None,
            faculty=None,
            orcid=None,
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    ]
    db_session.add_all(lecturers)
    db_session.flush()
    for lecturer, author, state in zip(
        lecturers,
        [approved_author, second_approved_author, candidate_author, rejected_author],
        ["APPROVED", "APPROVED", "CANDIDATE", "REJECTED"],
        strict=True,
    ):
        db_session.add(
            LecturerScopusIdentity(
                id=uuid.uuid4(),
                lecturer_id=lecturer.id,
                scopus_author_id=author.id,
                status=state,
                version=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

    first_import = ScopusImport(
        id=uuid.uuid4(),
        file_name="first.csv",
        file_sha256="a" * 64,
        total_records=1,
        valid_records=1,
        invalid_records=0,
        status="APPLIED",
        error_summary={"must_not": "be exposed"},
        normalization_summary={"also": "hidden"},
        version=1,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    second_import = ScopusImport(
        id=uuid.uuid4(),
        file_name="second.csv",
        file_sha256="b" * 64,
        total_records=1,
        valid_records=1,
        invalid_records=0,
        status="APPLIED",
        version=1,
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    db_session.add_all([first_import, second_import])
    db_session.flush()
    first_raw = RawScopusRecord(
        id=uuid.uuid4(),
        import_id=first_import.id,
        row_number=7,
        row_hash="c" * 64,
        eid_raw=publications["alpha"].eid,
        doi_raw=publications["alpha"].doi,
        raw_payload={"secret": "raw payload"},
        validation_status="VALID",
        validation_errors=[{"secret": "error"}],
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    second_raw = RawScopusRecord(
        id=uuid.uuid4(),
        import_id=second_import.id,
        row_number=3,
        row_hash="d" * 64,
        eid_raw=publications["alpha"].eid,
        doi_raw=publications["alpha"].doi,
        raw_payload={"secret": "new raw payload"},
        validation_status="VALID",
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
    )
    db_session.add_all([first_raw, second_raw])
    db_session.flush()
    db_session.add_all(
        [
            PublicationRawSource(
                id=uuid.uuid4(),
                publication_id=publications["alpha"].id,
                raw_record_id=first_raw.id,
                created_at=datetime(2024, 1, 2, tzinfo=UTC),
            ),
            PublicationRawSource(
                id=uuid.uuid4(),
                publication_id=publications["alpha"].id,
                raw_record_id=second_raw.id,
                created_at=datetime(2024, 2, 2, tzinfo=UTC),
            ),
        ]
    )
    db_session.commit()
    return publications


def _get(client: TestClient, role: str, path: str, authenticate) -> object:
    authenticate(role)
    return client.get(path)


@pytest.fixture
def edge_identities(db_session: Session) -> dict[str, Publication]:
    """Dedicated publication exercising revoked and multi-approved identities.

    One lecturer owns TWO APPROVED identities at different author positions.
    A REVOKED identity is linked to the same publication but must never appear
    in approved_lecturer_links.
    """

    publication = _publication(
        "EID-EDGE-1",
        "Edge Identity Study",
        year=2024,
        doi="10.1000/edge",
        source_title="Journal Edge",
        cited_by_count=0,
        document_type="Conference Paper",
        publication_stage="Final",
        open_access_status="Open",
    )
    db_session.add(publication)

    shared_lecturer = Lecturer(
        id=uuid.uuid4(),
        staff_code="CB-100",
        full_name="Lecturer Shared",
        full_name_normalized="lecturer shared",
        department="Software Engineering",
        faculty="ICT",
        orcid="0000-0002-1825-0098",
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    revoked_lecturer = Lecturer(
        id=uuid.uuid4(),
        staff_code="CB-101",
        full_name="Lecturer Revoked",
        full_name_normalized="lecturer revoked",
        department=None,
        faculty=None,
        orcid=None,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add_all([shared_lecturer, revoked_lecturer])

    first_author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id="2001",
        preferred_name="Shared Position One",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    second_author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id="2002",
        preferred_name="Shared Position Five",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    revoked_author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id="2003",
        preferred_name="Revoked Position",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add_all([first_author, second_author, revoked_author])
    db_session.flush()

    db_session.add_all(
        [
            PublicationAuthor(
                id=uuid.uuid4(),
                publication_id=publication.id,
                scopus_author_id=first_author.id,
                author_order=1,
                created_at=datetime.now(UTC),
            ),
            PublicationAuthor(
                id=uuid.uuid4(),
                publication_id=publication.id,
                scopus_author_id=revoked_author.id,
                author_order=3,
                created_at=datetime.now(UTC),
            ),
            PublicationAuthor(
                id=uuid.uuid4(),
                publication_id=publication.id,
                scopus_author_id=second_author.id,
                author_order=5,
                created_at=datetime.now(UTC),
            ),
        ]
    )
    db_session.add_all(
        [
            LecturerScopusIdentity(
                id=uuid.uuid4(),
                lecturer_id=shared_lecturer.id,
                scopus_author_id=first_author.id,
                status="APPROVED",
                version=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            LecturerScopusIdentity(
                id=uuid.uuid4(),
                lecturer_id=shared_lecturer.id,
                scopus_author_id=second_author.id,
                status="APPROVED",
                version=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            LecturerScopusIdentity(
                id=uuid.uuid4(),
                lecturer_id=revoked_lecturer.id,
                scopus_author_id=revoked_author.id,
                status="REVOKED",
                version=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ]
    )
    db_session.commit()
    return {"publication": publication}


@pytest.mark.parametrize("role", ["ADMIN", "REVIEWER"])
def test_list_allows_admin_and_reviewer(
    client: TestClient, authenticate, role: str, catalog
) -> None:
    response = _get(client, role, "/api/v1/publications", authenticate)
    assert response.status_code == 200
    assert response.json()["total"] == 5


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/publications")
    assert response.status_code == 401


def test_list_forbids_lecturer(client: TestClient, authenticate) -> None:
    response = _get(client, "LECTURER", "/api/v1/publications", authenticate)
    assert response.status_code == 403


def test_list_empty_catalog(client: TestClient, authenticate) -> None:
    response = _get(client, "ADMIN", "/api/v1/publications", authenticate)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ({"page": "0"}, 422),
        ({"page_size": "0"}, 422),
        ({"page_size": "101"}, 422),
        ({"q": "x" * 256}, 422),
    ],
)
def test_list_validates_pagination_and_q(
    client: TestClient, authenticate, catalog, query: dict[str, str], expected: int
) -> None:
    authenticate("ADMIN")
    response = client.get("/api/v1/publications", params=query)
    assert response.status_code == expected


def test_list_order_and_pagination_total_before_page(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("ADMIN")
    response = client.get(
        "/api/v1/publications", params={"page": 2, "page_size": 2}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert [item["eid"] for item in body["items"]] == ["EID-2023-G", "EID-2022-E"]


@pytest.mark.parametrize(
    "q",
    ["alpha methods", "eid-2024-a", "10.1000/alpha", "journal a", "ALPHA"],
)
def test_q_is_case_insensitive_across_literal_fields(
    client: TestClient, authenticate, catalog, q: str
) -> None:
    authenticate("REVIEWER")
    response = client.get("/api/v1/publications", params={"q": q})
    assert response.status_code == 200
    assert [item["eid"] for item in response.json()["items"]] == ["EID-2024-A"]


def test_q_trims_blank_and_escapes_like_wildcards(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("ADMIN")
    blank = client.get("/api/v1/publications", params={"q": "   "})
    wildcard = client.get("/api/v1/publications", params={"q": "%"})
    assert blank.json()["total"] == 5
    assert wildcard.json()["total"] == 0


@pytest.mark.parametrize(
    ("parameter", "value", "expected"),
    [
        ("year", "2024", ["EID-2024-A", "EID-2024-B"]),
        ("document_type", "Conference Paper", ["EID-2024-B"]),
        ("publication_stage", "Article in Press", ["EID-2024-B"]),
        ("open_access_status", "Closed", ["EID-2024-B"]),
        (
            "document_type",
            "   ",
            ["EID-2024-A", "EID-2024-B", "EID-2023-G", "EID-2022-E", "EID-NULL-D"],
        ),
    ],
)
def test_exact_filters_are_trimmed_and_null_safe(
    client: TestClient,
    authenticate,
    catalog,
    parameter: str,
    value: str,
    expected: list[str],
) -> None:
    authenticate("ADMIN")
    response = client.get("/api/v1/publications", params={parameter: value})
    assert response.status_code == 200
    assert [item["eid"] for item in response.json()["items"]] == expected


def test_list_preserves_null_fields(client: TestClient, authenticate, catalog) -> None:
    authenticate("ADMIN")
    response = client.get(
        "/api/v1/publications", params={"q": "Epsilon", "page_size": 1}
    )
    item = response.json()["items"][0]
    assert item["doi"] is None
    assert item["cited_by_count"] == 1


def test_list_preserves_null_citation(client: TestClient, authenticate, catalog) -> None:
    authenticate("ADMIN")
    response = client.get("/api/v1/publications", params={"q": "Delta"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["eid"] for item in items] == ["EID-NULL-D"]
    assert items[0]["cited_by_count"] is None


def test_list_preserves_zero_citation(client: TestClient, authenticate, catalog) -> None:
    authenticate("ADMIN")
    response = client.get("/api/v1/publications", params={"q": "EID-2024-B"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["eid"] for item in items] == ["EID-2024-B"]
    item = items[0]
    assert "cited_by_count" in item
    assert item["cited_by_count"] == 0
    assert item["cited_by_count"] is not None
    assert item["cited_by_count"] is not False


def test_list_null_year_is_preserved_and_ordered_last(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("ADMIN")
    response = client.get("/api/v1/publications", params={"page_size": 100})
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["eid"] for item in items] == [
        "EID-2024-A",
        "EID-2024-B",
        "EID-2023-G",
        "EID-2022-E",
        "EID-NULL-D",
    ]
    null_year_items = [item for item in items if item["year"] is None]
    assert len(null_year_items) == 1
    assert null_year_items[0]["eid"] == "EID-NULL-D"
    assert null_year_items[0]["year"] is None
    assert items[-1] is null_year_items[0]


def test_list_combined_filters_use_and_semantics(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("ADMIN")
    response = client.get(
        "/api/v1/publications",
        params={"year": "2024", "document_type": "Conference Paper"},
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["eid"] for item in body["items"]] == ["EID-2024-B"]
    assert body["total"] == 1

    narrowed = client.get(
        "/api/v1/publications",
        params={
            "year": "2024",
            "document_type": "Conference Paper",
            "publication_stage": "Article in Press",
            "open_access_status": "Closed",
        },
    )
    assert narrowed.status_code == 200
    narrowed_body = narrowed.json()
    assert [item["eid"] for item in narrowed_body["items"]] == ["EID-2024-B"]
    assert narrowed_body["total"] == 1

    conflicting = client.get(
        "/api/v1/publications",
        params={"year": "2024", "document_type": "Review"},
    )
    assert conflicting.status_code == 200
    conflict_body = conflicting.json()
    assert conflict_body["items"] == []
    assert conflict_body["total"] == 0


def test_list_filtered_total_counts_before_pagination(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("ADMIN")
    unfiltered = client.get("/api/v1/publications", params={"q": "journal"})
    assert unfiltered.status_code == 200
    assert unfiltered.json()["total"] == 4

    response = client.get(
        "/api/v1/publications", params={"q": "journal", "page": 1, "page_size": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] == 4
    assert body["total"] != 1
    assert body["page"] == 1
    assert body["page_size"] == 1


@pytest.mark.parametrize("role", ["ADMIN", "REVIEWER"])
def test_detail_auth_and_metadata(
    client: TestClient, authenticate, catalog, role: str
) -> None:
    response = _get(client, role, "/api/v1/publications/EID-2024-A", authenticate)
    assert response.status_code == 200
    body = response.json()
    assert body["eid"] == "EID-2024-A"
    assert body["title"] == "Alpha Methods"
    assert body["year"] == 2024
    assert body["cited_by_count"] == 5
    assert body["volume"] is None


def test_detail_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/publications/EID-2024-A")
    assert response.status_code == 401


def test_detail_forbids_lecturer(client: TestClient, authenticate) -> None:
    response = _get(
        client, "LECTURER", "/api/v1/publications/EID-2024-A", authenticate
    )
    assert response.status_code == 403


def test_detail_unknown_eid_is_stable_404(client: TestClient, authenticate) -> None:
    response = _get(
        client, "ADMIN", "/api/v1/publications/does-not-exist", authenticate
    )
    assert response.status_code == 404
    assert response.json()["code"] == "PUBLICATION_NOT_FOUND"


def test_detail_looks_up_eid_not_internal_uuid(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("ADMIN")
    response = client.get(f"/api/v1/publications/{catalog['alpha'].id}")
    assert response.status_code == 404


def test_detail_orders_authors_and_exposes_no_internal_ids(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("REVIEWER")
    body = client.get("/api/v1/publications/EID-2024-A").json()
    assert [author["author_order"] for author in body["authors"]] == [1, 2, 3, 5]
    assert [author["scopus_id"] for author in body["authors"]] == [
        "1001",
        "1003",
        "1004",
        "1002",
    ]
    assert all("id" not in author for author in body["authors"])


def test_detail_includes_only_approved_links_and_preserves_positions(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("ADMIN")
    body = client.get("/api/v1/publications/EID-2024-A").json()
    assert [
        (link["author_order"], link["scopus_id"])
        for link in body["approved_lecturer_links"]
    ] == [
        (1, "1001"),
        (5, "1002"),
    ]
    assert all("id" not in link for link in body["approved_lecturer_links"])
    assert all(
        link["full_name"] != "Lecturer Candidate"
        for link in body["approved_lecturer_links"]
    )
    assert all(
        link["full_name"] != "Lecturer Rejected"
        for link in body["approved_lecturer_links"]
    )


def test_detail_provenance_is_safe_and_deterministic(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("ADMIN")
    body = client.get("/api/v1/publications/EID-2024-A").json()
    assert [(row["file_name"], row["row_number"]) for row in body["provenance"]] == [
        ("first.csv", 7),
        ("second.csv", 3),
    ]
    assert body["provenance"][0]["file_sha256"] == "a" * 64
    assert all(
        set(row) == {"file_name", "file_sha256", "row_number", "imported_at"}
        for row in body["provenance"]
    )


def test_detail_excludes_raw_validation_and_audit_data(
    client: TestClient, authenticate, catalog
) -> None:
    authenticate("REVIEWER")
    body = client.get("/api/v1/publications/EID-2024-A").json()
    forbidden = {
        "raw_payload",
        "validation_errors",
        "error_summary",
        "normalization_summary",
        "row_hash",
        "audit",
        "id",
    }
    serialized = str(body)
    assert "raw payload" not in serialized
    assert "must_not" not in serialized
    assert forbidden.isdisjoint(body)
    assert all(forbidden.isdisjoint(row) for row in body["provenance"])


def test_detail_preserves_null_semantics(client: TestClient, authenticate, catalog) -> None:
    authenticate("ADMIN")
    body = client.get("/api/v1/publications/EID-NULL-D").json()
    assert body["year"] is None
    assert body["cited_by_count"] is None
    assert body["authors"] == []
    assert body["approved_lecturer_links"] == []
    assert body["provenance"] == []


def test_detail_preserves_zero_citation(client: TestClient, authenticate, catalog) -> None:
    authenticate("ADMIN")
    response = client.get("/api/v1/publications/EID-2024-B")
    assert response.status_code == 200
    body = response.json()
    assert body["eid"] == "EID-2024-B"
    assert "cited_by_count" in body
    assert body["cited_by_count"] == 0
    assert body["cited_by_count"] is not None


def test_detail_revoked_identity_is_not_an_approved_link(
    client: TestClient, authenticate, edge_identities
) -> None:
    authenticate("ADMIN")
    response = client.get("/api/v1/publications/EID-EDGE-1")
    assert response.status_code == 200
    body = response.json()

    author_scopus_ids = [author["scopus_id"] for author in body["authors"]]
    assert "2003" in author_scopus_ids

    link_scopus_ids = [link["scopus_id"] for link in body["approved_lecturer_links"]]
    assert "2003" not in link_scopus_ids
    assert all(
        link["full_name"] != "Lecturer Revoked"
        for link in body["approved_lecturer_links"]
    )


def test_detail_multi_approved_identities_for_same_lecturer(
    client: TestClient, authenticate, edge_identities
) -> None:
    authenticate("ADMIN")
    response = client.get("/api/v1/publications/EID-EDGE-1")
    assert response.status_code == 200
    body = response.json()

    links = body["approved_lecturer_links"]
    assert [
        (link["author_order"], link["scopus_id"], link["full_name"]) for link in links
    ] == [
        (1, "2001", "Lecturer Shared"),
        (5, "2002", "Lecturer Shared"),
    ]


def test_detail_database_errors_map_to_stable_503(
    client: TestClient, authenticate, catalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate("ADMIN")

    def fail(*_args, **_kwargs):
        raise OperationalError("select", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(
        publications_endpoint, "get_publication_detail", fail
    )
    response = client.get("/api/v1/publications/EID-2024-A")
    assert response.status_code == 503
    assert response.json()["code"] == "DATABASE_UNAVAILABLE"


def test_api_is_read_only(client: TestClient, authenticate, catalog, db_session: Session) -> None:
    authenticate("ADMIN")
    before = {
        "publications": db_session.scalar(select(func.count()).select_from(Publication)),
        "authors": db_session.scalar(select(func.count()).select_from(PublicationAuthor)),
        "raw_sources": db_session.scalar(select(func.count()).select_from(PublicationRawSource)),
    }
    assert client.get("/api/v1/publications").status_code == 200
    assert client.get("/api/v1/publications/EID-2024-A").status_code == 200
    db_session.expire_all()
    after = {
        "publications": db_session.scalar(select(func.count()).select_from(Publication)),
        "authors": db_session.scalar(select(func.count()).select_from(PublicationAuthor)),
        "raw_sources": db_session.scalar(select(func.count()).select_from(PublicationRawSource)),
    }
    assert after == before
    assert not db_session.new


def test_database_errors_map_to_stable_503(
    client: TestClient, authenticate, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate("ADMIN")

    def fail(*_args, **_kwargs):
        raise OperationalError("select", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(publications_endpoint, "list_publications", fail)
    response = client.get("/api/v1/publications")
    assert response.status_code == 503
    assert response.json()["code"] == "DATABASE_UNAVAILABLE"


def test_openapi_contains_publication_paths() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/publications" in paths
    assert "/api/v1/publications/{eid}" in paths
    # A4 export route registered (static /export before dynamic /{eid})
    assert "/api/v1/publications/export" in paths
    assert "get" in paths["/api/v1/publications"]
    assert "get" in paths["/api/v1/publications/{eid}"]
    assert "get" in paths["/api/v1/publications/export"]
