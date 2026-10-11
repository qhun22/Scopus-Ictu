"""An unlinked LECTURER (no lecturer profile, no JSON) exists, can look up, and gets nothing implicit."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.models.governance import User


@pytest.fixture
def db() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    schema = f"test_unlinked_{uuid.uuid4().hex}"
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
def lecturer(db: Session) -> User:
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4(), email="b@unlinked.test", password_hash="x", display_name="B", role="LECTURER",
                lecturer_id=None, is_active=True, version=1, auth_version=1, created_at=now, updated_at=now)
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def client(db: Session, lecturer: User) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: lecturer
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_account_without_profile_can_be_stored(db: Session, lecturer: User) -> None:
    assert db.query(User).filter_by(role="LECTURER", lecturer_id=None).count() == 1


def test_lookup_works_and_nothing_personal_is_implied(client: TestClient) -> None:
    assert client.get("/api/v1/publications").status_code == 200
    assert client.get("/api/v1/search", params={"q": "zz"}).status_code == 200
    # No identity is ever attached implicitly: the personal endpoints say "not linked".
    for path in ("/api/v1/lecturers/me/profile", "/api/v1/lecturers/me/identities", "/api/v1/lecturers/me/publications"):
        response = client.get(path)
        assert response.status_code == 403 and response.json()["code"] == "LECTURER_NOT_LINKED", path


def test_lecturer_cannot_use_administrative_endpoints(client: TestClient) -> None:
    for path in (
        "/api/v1/users", "/api/v1/lecturers", "/api/v1/audits", "/api/v1/authors", "/api/v1/imports",
        "/api/v1/dashboard/summary", "/api/v1/reviews/candidates", "/api/v1/affiliations/overview",
        "/api/v1/publications/export",
    ):
        status = client.get(path).status_code
        assert status in (403, 404), (path, status)
    for path in ("/api/v1/users", "/api/v1/imports", "/api/v1/affiliations/overview", "/api/v1/authors"):
        assert client.get(path).status_code == 403, path
    assert client.post("/api/v1/affiliations/preview").status_code == 403
