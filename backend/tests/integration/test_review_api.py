"""HTTP contract tests for the M2.7B-5 review boundary."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.v1.endpoints.reviews as reviews_endpoint
from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.governance import User
from app.services.candidate_review_service import AcceptResult


def _user(role: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=f"{role.lower()}@review.test",
        password_hash="not-used",
        display_name=f"Synthetic {role}",
        role=role,
        lecturer_id=uuid.uuid4() if role == "LECTURER" else None,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_openapi_contains_all_review_operations(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/reviews/candidates" in paths
    assert "/api/v1/reviews/candidates/{candidate_id}" in paths
    assert "/api/v1/reviews/candidates/{candidate_id}/reviews" in paths


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/v1/reviews/candidates", None),
        ("get", f"/api/v1/reviews/candidates/{uuid.uuid4()}", None),
        (
            "post",
            f"/api/v1/reviews/candidates/{uuid.uuid4()}/reviews",
            {
                "observation_id": str(uuid.uuid4()),
                "candidate_version": 1,
                "action": "ACCEPT",
            },
        ),
    ],
)
def test_lecturer_cannot_access_review_api(
    client: TestClient, method: str, path: str, body: dict | None
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user("LECTURER")
    app.dependency_overrides[get_session] = lambda: MagicMock()

    response = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_decision_rejects_identity_and_evidence_injection(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user("REVIEWER")
    app.dependency_overrides[get_session] = lambda: MagicMock()

    response = client.post(
        f"/api/v1/reviews/candidates/{uuid.uuid4()}/reviews",
        json={
            "observation_id": str(uuid.uuid4()),
            "candidate_version": 1,
            "action": "ACCEPT",
            "reviewer_user_id": str(uuid.uuid4()),
            "identity_id": str(uuid.uuid4()),
            "confidence_score": 0.99,
            "evidence_snapshot": {},
        },
    )

    assert response.status_code == 422


def test_decision_uses_authenticated_reviewer_and_domain_service(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewer = _user("REVIEWER")
    db = MagicMock()
    candidate_id = uuid.uuid4()
    observation_id = uuid.uuid4()
    captured = {}

    class FakeReviewService:
        def __init__(self, _db):
            pass

        def accept_candidate(self, command):
            captured["command"] = command
            return AcceptResult(
                review_id=uuid.uuid4(),
                candidate_id=candidate_id,
                observation_id=observation_id,
                action="ACCEPT",
                candidate_status="ACCEPTED",
                candidate_version=2,
                idempotent=False,
                resulting_identity_id=uuid.uuid4(),
            )

    app.dependency_overrides[get_current_user] = lambda: reviewer
    app.dependency_overrides[get_session] = lambda: db
    monkeypatch.setattr(reviews_endpoint, "CandidateReviewService", FakeReviewService)

    response = client.post(
        f"/api/v1/reviews/candidates/{candidate_id}/reviews",
        json={
            "observation_id": str(observation_id),
            "candidate_version": 1,
            "action": "ACCEPT",
        },
    )

    assert response.status_code == 200
    assert captured["command"].reviewer_user_id == reviewer.id
    assert response.json()["idempotent"] is False
    db.add.assert_not_called()
    db.commit.assert_not_called()
