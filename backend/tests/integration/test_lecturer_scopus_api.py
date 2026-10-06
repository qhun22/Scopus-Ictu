"""HTTP contract tests for the M2.8-A2 lecturer Scopus read API."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.v1.endpoints.lecturer_scopus as lecturer_scopus_endpoint
from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.governance import User
from app.schemas.lecturer_scopus_projection import (
    ApprovedIdentitySummaryRead,
    IdentityEvidenceSummaryRead,
    LecturerProfileRead,
    LecturerPublicationAggregatesRead,
    LecturerPublicationRead,
    PaginatedLecturerPublicationsRead,
)


def _user(role: str, lecturer_id: uuid.UUID | None = None) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@api.test",
        password_hash="not-used",
        display_name=f"Synthetic {role}",
        role=role,
        lecturer_id=lecturer_id,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=now,
        updated_at=now,
    )


def _profile(lecturer_id: uuid.UUID, name: str = "Lecturer A") -> LecturerProfileRead:
    return LecturerProfileRead(
        lecturer_id=lecturer_id,
        full_name=name,
        staff_code="CB-001",
        email="lecturer-a@ictu.edu.vn",
        academic_rank="TS",
        academic_degree="PhD",
        position="Lecturer",
        department="Software Engineering",
        faculty="Information Technology",
        repository_profile_url="https://repository.example/lecturer-a",
        orcid="0000-0002-1825-0097",
    )


def _identity(name: str = "Approved Author") -> ApprovedIdentitySummaryRead:
    now = datetime.now(UTC)
    return ApprovedIdentitySummaryRead(
        identity_id=uuid.uuid4(),
        status="APPROVED",
        scopus_author_id=uuid.uuid4(),
        scopus_id="12345678901",
        preferred_name=name,
        name_variants=[name],
        evidence=[
            IdentityEvidenceSummaryRead(
                evidence_type="NAME_SIMILARITY",
                direction="SUPPORTS",
                created_at=now,
            )
        ],
        created_at=now,
        updated_at=now,
    )


def _publication_page(
    *,
    page: int = 1,
    page_size: int = 20,
    total: int = 1,
    empty: bool = False,
) -> PaginatedLecturerPublicationsRead:
    items: list[LecturerPublicationRead] = []
    if not empty:
        items.append(
            LecturerPublicationRead(
                publication_id=uuid.uuid4(),
                eid="2-s2.0-API-1",
                doi="10.1234/api-1",
                title="API publication",
                source_title="ICTU Journal",
                year=2024,
                cited_by_count=4,
                document_type="Article",
                publication_stage="Final",
                open_access_status="Open",
                linked_author_orders=[1, 2],
            )
        )
    return PaginatedLecturerPublicationsRead(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


def _aggregates(
    *,
    total: int = 1,
    approved_identity_count: int = 1,
) -> LecturerPublicationAggregatesRead:
    return LecturerPublicationAggregatesRead(
        total_publications=total,
        publication_count_by_year={2024: total} if total else {},
        unknown_year_count=0,
        known_citation_sum=4 if total else 0,
        citation_unknown_publication_count=0,
        approved_identity_count=approved_identity_count,
    )


class FakeProjectionService:
    def __init__(
        self,
        *,
        profiles: dict[uuid.UUID, LecturerProfileRead] | None = None,
        identities: dict[uuid.UUID, list[ApprovedIdentitySummaryRead]] | None = None,
        page: PaginatedLecturerPublicationsRead | None = None,
        aggregates: LecturerPublicationAggregatesRead | None = None,
        state: dict[str, int] | None = None,
    ) -> None:
        self.profiles = profiles or {}
        self.identities = identities or {}
        self.page = page or _publication_page()
        self.aggregates = aggregates or _aggregates()
        self.calls: list[tuple[str, uuid.UUID]] = []
        self.state = state

    def get_lecturer_profile(self, lecturer_id: uuid.UUID):
        self.calls.append(("profile", lecturer_id))
        return self.profiles.get(lecturer_id)

    def get_approved_identity_summaries(self, lecturer_id: uuid.UUID):
        self.calls.append(("identities", lecturer_id))
        return self.identities.get(lecturer_id, [])

    def get_lecturer_publications(
        self, lecturer_id: uuid.UUID, *, page: int = 1, page_size: int = 20
    ):
        self.calls.append(("publications", lecturer_id))
        result = self.page.model_copy(deep=True)
        result.page = page
        result.page_size = page_size
        return result

    def get_lecturer_publication_aggregates(self, lecturer_id: uuid.UUID):
        self.calls.append(("aggregates", lecturer_id))
        return self.aggregates


@pytest.fixture
def db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(db: MagicMock):
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _authenticate(role: str, lecturer_id: uuid.UUID | None = None) -> User:
    user = _user(role, lecturer_id)
    app.dependency_overrides[get_current_user] = lambda: user
    return user


def _install_projection(
    monkeypatch: pytest.MonkeyPatch, service: FakeProjectionService
) -> None:
    monkeypatch.setattr(
        lecturer_scopus_endpoint,
        "LecturerScopusProjectionService",
        lambda _db: service,
    )


def test_a2_t01_unauthenticated_me_profile(client: TestClient) -> None:
    response = client.get("/api/v1/lecturers/me/profile")

    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"


def test_a2_t02_lecturer_own_profile(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer_id = uuid.uuid4()
    service = FakeProjectionService(profiles={lecturer_id: _profile(lecturer_id)})
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER", lecturer_id)

    response = client.get("/api/v1/lecturers/me/profile")

    assert response.status_code == 200
    assert response.json()["lecturer_id"] == str(lecturer_id)
    assert response.json()["full_name"] == "Lecturer A"


def test_a2_t03_lecturer_not_linked(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = FakeProjectionService()
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER")

    response = client.get("/api/v1/lecturers/me/profile")

    assert response.status_code == 403
    assert response.json()["code"] == "LECTURER_NOT_LINKED"
    assert service.calls == []


def test_a2_t04_lecturer_own_identities(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer_id = uuid.uuid4()
    approved = _identity()
    service = FakeProjectionService(identities={lecturer_id: [approved]})
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER", lecturer_id)

    response = client.get("/api/v1/lecturers/me/identities")

    assert response.status_code == 200
    assert response.json()[0]["status"] == "APPROVED"
    assert len(response.json()) == 1


def test_a2_t05_lecturer_own_publications(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer_id = uuid.uuid4()
    service = FakeProjectionService(
        page=_publication_page(page=2, page_size=1, total=3),
        aggregates=_aggregates(total=3),
    )
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER", lecturer_id)

    response = client.get(
        "/api/v1/lecturers/me/publications", params={"page": 2, "page_size": 1}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    assert payload["aggregates"]["total_publications"] == 3


def test_a2_t06_empty_identity_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer_id = uuid.uuid4()
    service = FakeProjectionService(identities={lecturer_id: []})
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER", lecturer_id)

    response = client.get("/api/v1/lecturers/me/identities")

    assert response.status_code == 200
    assert response.json() == []


def test_a2_t07_empty_publication_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = FakeProjectionService(
        page=_publication_page(total=0, empty=True),
        aggregates=_aggregates(total=0, approved_identity_count=1),
    )
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER", uuid.uuid4())

    response = client.get("/api/v1/lecturers/me/publications")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0
    assert response.json()["aggregates"]["approved_identity_count"] == 1


def test_a2_t08_reviewer_me_denied(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = FakeProjectionService()
    _install_projection(monkeypatch, service)
    _authenticate("REVIEWER")

    response = client.get("/api/v1/lecturers/me/profile")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_a2_t09_admin_me_denied(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = FakeProjectionService()
    _install_projection(monkeypatch, service)
    _authenticate("ADMIN")

    response = client.get("/api/v1/lecturers/me/profile")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_a2_t10_admin_target_profile(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer_id = uuid.uuid4()
    service = FakeProjectionService(profiles={lecturer_id: _profile(lecturer_id)})
    _install_projection(monkeypatch, service)
    _authenticate("ADMIN")

    response = client.get(f"/api/v1/lecturers/{lecturer_id}/scopus/profile")

    assert response.status_code == 200
    assert response.json()["lecturer_id"] == str(lecturer_id)


def test_a2_t11_admin_target_identities(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer_id = uuid.uuid4()
    service = FakeProjectionService(
        profiles={lecturer_id: _profile(lecturer_id)},
        identities={lecturer_id: [_identity()]},
    )
    _install_projection(monkeypatch, service)
    _authenticate("ADMIN")

    response = client.get(f"/api/v1/lecturers/{lecturer_id}/scopus/identities")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert [call[0] for call in service.calls] == ["profile", "identities"]


def test_a2_t12_admin_target_publications(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer_id = uuid.uuid4()
    service = FakeProjectionService(
        profiles={lecturer_id: _profile(lecturer_id)},
        page=_publication_page(page=2, page_size=2, total=5),
        aggregates=_aggregates(total=5),
    )
    _install_projection(monkeypatch, service)
    _authenticate("ADMIN")

    response = client.get(
        f"/api/v1/lecturers/{lecturer_id}/scopus/publications",
        params={"page": 2, "page_size": 2},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 5
    assert response.json()["aggregates"]["total_publications"] == 5


def test_a2_t13_admin_target_not_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = FakeProjectionService()
    _install_projection(monkeypatch, service)
    _authenticate("ADMIN")

    response = client.get(f"/api/v1/lecturers/{uuid.uuid4()}/scopus/profile")

    assert response.status_code == 404
    assert response.json()["code"] == "LECTURER_NOT_FOUND"


@pytest.mark.parametrize("role", ["LECTURER", "REVIEWER"])
def test_a2_target_routes_denied_to_non_admin(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    service = FakeProjectionService()
    _install_projection(monkeypatch, service)
    _authenticate(role, uuid.uuid4() if role == "LECTURER" else None)

    response = client.get(f"/api/v1/lecturers/{uuid.uuid4()}/scopus/profile")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert service.calls == []


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 0}, {"page_size": 101}],
)
def test_a2_t16_to_t18_pagination_validation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    params: dict[str, int],
) -> None:
    service = FakeProjectionService()
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER", uuid.uuid4())

    response = client.get("/api/v1/lecturers/me/publications", params=params)

    assert response.status_code == 422
    assert service.calls == []


def test_a2_t19_publication_aggregates_cover_full_result_set(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = FakeProjectionService(
        page=_publication_page(page=1, page_size=1, total=5),
        aggregates=_aggregates(total=5),
    )
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER", uuid.uuid4())

    response = client.get(
        "/api/v1/lecturers/me/publications", params={"page_size": 1}
    )

    payload = response.json()
    assert response.status_code == 200
    assert len(payload["items"]) == 1
    assert payload["total"] == 5
    assert payload["aggregates"]["total_publications"] == 5


def test_a2_t20_safe_identity_serialization(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer_id = uuid.uuid4()
    service = FakeProjectionService(identities={lecturer_id: [_identity()]})
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER", lecturer_id)

    response = client.get("/api/v1/lecturers/me/identities")
    serialized = json.dumps(response.json())

    assert response.status_code == 200
    for forbidden in (
        "features",
        "algorithm_version",
        "evidence_fingerprint",
        "source_refs",
        "confidence_score",
    ):
        assert forbidden not in serialized


def test_a2_t21_no_cross_lecturer_leak(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer_a = uuid.uuid4()
    lecturer_b = uuid.uuid4()
    service = FakeProjectionService(
        profiles={lecturer_a: _profile(lecturer_a, "Lecturer A")},
        identities={lecturer_a: [_identity("Author A")]},
    )
    _install_projection(monkeypatch, service)
    _authenticate("LECTURER", lecturer_a)

    profile_response = client.get("/api/v1/lecturers/me/profile")
    identity_response = client.get("/api/v1/lecturers/me/identities")
    combined = json.dumps([profile_response.json(), identity_response.json()])

    assert str(lecturer_a) in combined
    assert str(lecturer_b) not in combined
    assert "Lecturer B" not in combined


def test_a2_t22_read_only_http(
    client: TestClient,
    db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecturer_id = uuid.uuid4()
    state = {"identity": 1, "evidence": 1, "reviews": 1, "audits": 1}
    service = FakeProjectionService(
        profiles={lecturer_id: _profile(lecturer_id)},
        identities={lecturer_id: [_identity()]},
        state=state,
    )
    _install_projection(monkeypatch, service)
    before = state.copy()

    _authenticate("LECTURER", lecturer_id)
    for path in (
        "/api/v1/lecturers/me/profile",
        "/api/v1/lecturers/me/identities",
        "/api/v1/lecturers/me/publications",
    ):
        assert client.get(path).status_code == 200

    _authenticate("ADMIN")
    for path in (
        f"/api/v1/lecturers/{lecturer_id}/scopus/profile",
        f"/api/v1/lecturers/{lecturer_id}/scopus/identities",
        f"/api/v1/lecturers/{lecturer_id}/scopus/publications",
    ):
        assert client.get(path).status_code == 200

    assert state == before
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


def test_a2_routes_registered_in_actual_fastapi_app(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    expected = {
        "/api/v1/lecturers/me/profile",
        "/api/v1/lecturers/me/identities",
        "/api/v1/lecturers/me/publications",
        "/api/v1/lecturers/{lecturer_id}/scopus/profile",
        "/api/v1/lecturers/{lecturer_id}/scopus/identities",
        "/api/v1/lecturers/{lecturer_id}/scopus/publications",
    }
    assert expected.issubset(paths)
