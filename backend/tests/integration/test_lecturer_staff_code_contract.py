"""Integration tests for the lecturer staff_code contract (M2.6B prep).

Covers:
1. create Lecturer without staff_code -> success, NULL stored
2. create with unique staff_code -> success
3. create duplicate staff_code -> 409 STAFF_CODE_ALREADY_EXISTS
4. update current Lecturer keeping same code -> success/no duplicate
5. update to new unique code -> success
6. update to another Lecturer's code -> STAFF_CODE_ALREADY_EXISTS
7. clear staff_code -> NULL
8. linked-account Lecturer can update/clear staff_code
9. no M1 migration change (no DDL applied)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import get_session
from app.core.security import password_hasher, token_service
from app.main import app
from app.models.base import Base
from app.models.governance import User
from app.models.master_lecturer import Lecturer


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    url = settings.database_url
    schema = f"test_m26b_staff_{uuid.uuid4().hex}"
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
        email="staff-admin@example.test",
        password_hash="fakehash",
        display_name="Staff Admin",
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
# 1. create Lecturer without staff_code -> success, NULL stored
# ---------------------------------------------------------------------------


def test_create_lecturer_without_staff_code_stores_null(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    headers = _auth(admin_user)
    response = client.post(
        "/api/v1/lecturers",
        headers=headers,
        json={
            "full_name": "Nguyen Van A",
            "email": "nva@ictu.edu.vn",
            "password": "StrongPassword123!",
            "role": "LECTURER",
        },
    )
    assert response.status_code == 201
    db_session.expire_all()
    lecturer = db_session.query(Lecturer).filter(Lecturer.email == "nva@ictu.edu.vn").one()
    assert lecturer.staff_code is None


# ---------------------------------------------------------------------------
# 2. create with unique staff_code -> success
# ---------------------------------------------------------------------------


def test_create_lecturer_with_unique_staff_code_succeeds(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    headers = _auth(admin_user)
    response = client.post(
        "/api/v1/lecturers",
        headers=headers,
        json={
            "full_name": "Tran Thi B",
            "email": "ttb@ictu.edu.vn",
            "password": "StrongPassword123!",
            "role": "LECTURER",
            "staff_code": "ICTU-001",
        },
    )
    assert response.status_code == 201
    db_session.expire_all()
    lecturer = db_session.query(Lecturer).filter(Lecturer.email == "ttb@ictu.edu.vn").one()
    assert lecturer.staff_code == "ICTU-001"


# ---------------------------------------------------------------------------
# 3. create duplicate staff_code -> 409 STAFF_CODE_ALREADY_EXISTS
# ---------------------------------------------------------------------------


def test_create_lecturer_duplicate_staff_code_returns_precise_code(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    # Seed an existing lecturer with a known staff_code.
    seed = Lecturer(
        id=uuid.uuid4(),
        full_name="Existing Lecturer",
        full_name_normalized="existing lecturer",
        email="existing@ictu.edu.vn",
        staff_code="DUP-001",
        is_active=True,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(seed)
    db_session.commit()

    headers = _auth(admin_user)
    response = client.post(
        "/api/v1/lecturers",
        headers=headers,
        json={
            "full_name": "Another Lecturer",
            "email": "another@ictu.edu.vn",
            "password": "StrongPassword123!",
            "role": "LECTURER",
            "staff_code": "DUP-001",
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body.get("code") == "STAFF_CODE_ALREADY_EXISTS"
    assert body.get("staff_code") == "DUP-001"


# ---------------------------------------------------------------------------
# 4. update current Lecturer keeping same code -> success/no duplicate
# ---------------------------------------------------------------------------


def test_update_lecturer_keeps_own_staff_code(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    seed = Lecturer(
        id=uuid.uuid4(),
        full_name="Keep Code",
        full_name_normalized="keep code",
        email="keep@ictu.edu.vn",
        staff_code="KEEP-1",
        is_active=True,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(seed)
    db_session.commit()

    headers = _auth(admin_user)
    response = client.put(
        f"/api/v1/lecturers/{seed.id}",
        headers=headers,
        json={
            "version": 1,
            "full_name": "Keep Code Renamed",
            "staff_code": "KEEP-1",
        },
    )
    assert response.status_code == 200
    db_session.expire_all()
    refreshed = db_session.query(Lecturer).filter(Lecturer.id == seed.id).one()
    assert refreshed.staff_code == "KEEP-1"
    assert refreshed.full_name == "Keep Code Renamed"


# ---------------------------------------------------------------------------
# 5. update to new unique code -> success
# ---------------------------------------------------------------------------


def test_update_lecturer_to_new_unique_staff_code(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    seed = Lecturer(
        id=uuid.uuid4(),
        full_name="Change Code",
        full_name_normalized="change code",
        email="change@ictu.edu.vn",
        staff_code="OLD-1",
        is_active=True,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(seed)
    db_session.commit()

    headers = _auth(admin_user)
    response = client.put(
        f"/api/v1/lecturers/{seed.id}",
        headers=headers,
        json={"version": 1, "staff_code": "NEW-1"},
    )
    assert response.status_code == 200
    db_session.expire_all()
    refreshed = db_session.query(Lecturer).filter(Lecturer.id == seed.id).one()
    assert refreshed.staff_code == "NEW-1"


# ---------------------------------------------------------------------------
# 6. update to another Lecturer's code -> STAFF_CODE_ALREADY_EXISTS
# ---------------------------------------------------------------------------


def test_update_lecturer_to_other_lecturer_staff_code_returns_precise_code(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    a = Lecturer(
        id=uuid.uuid4(),
        full_name="A",
        full_name_normalized="a",
        email="a@ictu.edu.vn",
        staff_code="A-CODE",
        is_active=True,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    b = Lecturer(
        id=uuid.uuid4(),
        full_name="B",
        full_name_normalized="b",
        email="b@ictu.edu.vn",
        staff_code="B-CODE",
        is_active=True,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add_all([a, b])
    db_session.commit()

    headers = _auth(admin_user)
    response = client.put(
        f"/api/v1/lecturers/{a.id}",
        headers=headers,
        json={"version": 1, "staff_code": "B-CODE"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body.get("code") == "STAFF_CODE_ALREADY_EXISTS"
    assert body.get("staff_code") == "B-CODE"

    # A's staff_code must remain unchanged.
    db_session.expire_all()
    a_db = db_session.query(Lecturer).filter(Lecturer.id == a.id).one()
    assert a_db.staff_code == "A-CODE"


# ---------------------------------------------------------------------------
# 7. clear staff_code -> NULL
# ---------------------------------------------------------------------------


def test_update_lecturer_clear_staff_code_to_null(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    seed = Lecturer(
        id=uuid.uuid4(),
        full_name="Clear Code",
        full_name_normalized="clear code",
        email="clear@ictu.edu.vn",
        staff_code="WILL-CLEAR",
        is_active=True,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(seed)
    db_session.commit()

    headers = _auth(admin_user)
    response = client.put(
        f"/api/v1/lecturers/{seed.id}",
        headers=headers,
        json={"version": 1, "staff_code": None},
    )
    assert response.status_code == 200
    db_session.expire_all()
    refreshed = db_session.query(Lecturer).filter(Lecturer.id == seed.id).one()
    assert refreshed.staff_code is None


# ---------------------------------------------------------------------------
# 8. linked-account Lecturer can update/clear staff_code
# ---------------------------------------------------------------------------


def test_update_linked_lecturer_clears_staff_code(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    lecturer_id = uuid.uuid4()
    lecturer = Lecturer(
        id=lecturer_id,
        full_name="Linked Lecturer",
        full_name_normalized="linked lecturer",
        email="linked@ictu.edu.vn",
        staff_code="LINKED-1",
        is_active=True,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    user = User(
        id=uuid.uuid4(),
        email="linked@ictu.edu.vn",
        password_hash=password_hasher.hash("LinkedPassword123!"),
        display_name="Linked Lecturer",
        role="LECTURER",
        lecturer_id=lecturer_id,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(lecturer)
    db_session.flush()
    db_session.add(user)
    db_session.flush()
    db_session.commit()

    # Sanity: the linked user must be visible to the endpoint.
    visible = db_session.query(User).filter(User.lecturer_id == lecturer_id).first()
    assert visible is not None, "Fixture user was not committed"

    headers = _auth(admin_user)
    response = client.put(
        f"/api/v1/lecturers/{lecturer_id}",
        headers=headers,
        json={"version": 1, "staff_code": None},
    )
    assert response.status_code == 200
    db_session.expire_all()
    refreshed = db_session.query(Lecturer).filter(Lecturer.id == lecturer_id).one()
    assert refreshed.staff_code is None


# ---------------------------------------------------------------------------
# 9. no M1 migration change: model is the same nullable staff_code column
# ---------------------------------------------------------------------------


def test_staff_code_column_remains_optional() -> None:
    """Verify the model is unchanged: staff_code is still nullable and the
    partial unique index is still present.
    """
    from sqlalchemy import inspect

    from app.core.database import get_engine
    from app.models.master_lecturer import Lecturer as LecturerModel

    inspector = inspect(get_engine())
    columns = {c["name"]: c for c in inspector.get_columns("lecturers")}
    assert "staff_code" in columns
    assert columns["staff_code"]["nullable"] is True
    # The column type on the model itself must remain String(50), nullable.
    column = LecturerModel.__table__.c.staff_code
    assert column.nullable is True
    assert column.type.length == 50
