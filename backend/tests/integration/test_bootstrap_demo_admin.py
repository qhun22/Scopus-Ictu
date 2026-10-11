"""Task 14: demo ADMIN bootstrap, login, role enforcement (isolated schema per test, synthetic values)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_session
from app.core.security import password_hasher
from app.main import app
from app.models.base import Base
from app.models.governance import AuditEvent, User
from app.models.master_lecturer import Lecturer
from scripts import bootstrap_demo_admin as boot
from scripts.generate_matching_candidates import CliRefused

EMAIL = "demo.admin@bootstrap.test"
PASSWORD = "p-demo"  # synthetic, shorter than the 8-char system policy on purpose


@pytest.fixture
def db() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("never target an acceptance database")
    schema = f"test_t14_boot_{uuid.uuid4().hex}"
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


def _url(database="scopus_x_demo_y", port=55432, host="127.0.0.1"):
    return make_url(f"postgresql+psycopg2://u:p@{host}:{port}/{database}")


def _guards(**kw):
    base = dict(environment="local", url=_url(), expected_database="scopus_x_demo_y", expected_port=55432,
                email=EMAIL, password=PASSWORD, allow_weak=True)
    base.update(kw)
    boot.validate_guards(**base)


def _lecturer_user(db: Session, email: str, password: str) -> User:
    profile = Lecturer(full_name="Giảng viên thử", full_name_normalized="giang vien thu")
    db.add(profile)
    db.flush()
    user = User(id=uuid.uuid4(), email=email, password_hash=password_hasher.hash(password), display_name="Giảng viên",
                role="LECTURER", lecturer_id=profile.id, is_active=True)
    db.add(user)
    db.commit()
    return user


# ------------------------------------------------------------------ guards
def test_guards_accept_only_the_isolated_local_demo_setup() -> None:
    _guards()
    for kw in (
        {"environment": "prod"},
        {"environment": "staging"},
        {"url": _url(port=5432), "expected_port": None},
        {"url": _url(host="10.0.0.9")},
        {"url": _url(database="scopus_production"), "expected_database": "scopus_production"},
        {"expected_database": "another_demo_db"},
        {"url": _url(database="scopus_ictu_acceptance_v2"), "expected_database": "scopus_ictu_acceptance_v2"},
        {"email": None},
        {"email": "not-an-email"},
        {"password": None},
        {"allow_weak": False},  # weak password without the explicit flag
    ):
        with pytest.raises(CliRefused):
            _guards(**kw)
    _guards(password="long-enough-pass", allow_weak=False)  # a policy-compliant password needs no flag


# ------------------------------------------------------------------ creation / idempotency
def test_create_is_admin_hashed_audited_and_idempotent(db) -> None:
    other = User(id=uuid.uuid4(), email="someone@else.test", password_hash=password_hasher.hash("another-password"),
                 display_name="Someone", role="REVIEWER", is_active=True)
    db.add(other)
    db.commit()
    before_other = (other.email, other.role, other.password_hash, other.version)

    plan = boot.plan_for(db, EMAIL, PASSWORD)
    assert plan.action == "CREATE"
    db.rollback()
    user = boot.create_admin(db, EMAIL, PASSWORD)
    assert user.role == "ADMIN" and user.is_active and user.lecturer_id is None
    assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash
    assert password_hasher.verify(PASSWORD, user.password_hash) and not password_hasher.verify("wrong", user.password_hash)
    audit = db.scalars(select(AuditEvent).where(AuditEvent.action == "DEMO_ADMIN_BOOTSTRAPPED")).all()
    assert len(audit) == 1 and PASSWORD not in str(audit[0].after_state) and "hash" not in str(audit[0].after_state).lower()

    # second run: nothing to create, nothing modified, no duplicate
    again = boot.plan_for(db, EMAIL.upper(), PASSWORD)
    assert again.action == "EXISTS_OK" and again.credential_matches is True
    assert db.scalar(select(func.count()).select_from(User).where(func.lower(User.email) == EMAIL)) == 1
    db.refresh(other)
    assert (other.email, other.role, other.password_hash, other.version) == before_other  # other accounts untouched


def test_existing_account_with_other_credentials_or_role_is_never_overwritten(db) -> None:
    lecturer = _lecturer_user(db, EMAIL, "original-secret")
    old_hash = lecturer.password_hash
    plan = boot.plan_for(db, EMAIL, PASSWORD)
    assert plan.action == "UNSUITABLE" and plan.credential_matches is False
    db.refresh(lecturer)
    assert lecturer.role == "LECTURER" and lecturer.password_hash == old_hash

    lecturer.role = "ADMIN"
    lecturer.lecturer_id = None  # an ADMIN with no lecturer link, other credential
    db.commit()
    plan = boot.plan_for(db, EMAIL, PASSWORD)
    assert plan.action == "EXISTS_OK" and plan.credential_matches is False and "NOT match" in plan.detail
    db.refresh(lecturer)
    assert lecturer.password_hash == old_hash  # a different credential is reported, not replaced


# ------------------------------------------------------------------ login + role enforcement through the real API
@pytest.fixture
def client(db) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_bootstrapped_admin_signs_in_and_every_admin_area_is_reachable(db, client) -> None:
    boot.create_admin(db, EMAIL, PASSWORD)
    _lecturer_user(db, "lecturer@bootstrap.test", "lecturer-pass-1")

    assert _login(client, EMAIL, "wrong").status_code == 401
    assert _login(client, "nobody@bootstrap.test", PASSWORD).status_code == 401
    ok = _login(client, EMAIL, PASSWORD)
    assert ok.status_code == 200 and ok.json()["role"] == "ADMIN" and ok.json()["display_name"] == "Quản trị viên"
    assert client.get("/api/v1/auth/me").json()["role"] == "ADMIN"
    for path in ("/api/v1/users", "/api/v1/lecturers", "/api/v1/publications", "/api/v1/reviews/candidates",
                 "/api/v1/reviews/history", "/api/v1/audits", "/api/v1/imports", "/api/v1/dashboard/summary",
                 "/api/v1/search?q=abc"):
        status = client.get(path).status_code
        assert status in (200, 404, 422), (path, status)  # reachable: never 401/403 for ADMIN
        assert status not in (401, 403)

    # the weak bootstrap password does NOT relax the API policy for resetting/creating credentials
    user_id = db.scalar(select(User.id).where(User.email == "lecturer@bootstrap.test"))
    r = client.post(f"/api/v1/users/{user_id}/reset-password", json={"version": 1, "new_password": "123"})
    assert r.status_code == 422


def test_lecturer_and_anonymous_have_no_admin_access(db, client) -> None:
    boot.create_admin(db, EMAIL, PASSWORD)
    _lecturer_user(db, "lecturer@bootstrap.test", "lecturer-pass-1")
    anonymous = TestClient(app, raise_server_exceptions=False)
    for path in ("/api/v1/users", "/api/v1/lecturers", "/api/v1/audits", "/api/v1/reviews/candidates"):
        assert anonymous.get(path).status_code == 401
    anonymous.close()
    assert _login(client, "lecturer@bootstrap.test", "lecturer-pass-1").status_code == 200
    for path in ("/api/v1/users", "/api/v1/lecturers", "/api/v1/audits", "/api/v1/reviews/candidates"):
        assert client.get(path).status_code == 403, path
    # Read-only academic lookup is deliberately open to LECTURER (decision 2026-10-11).
    assert client.get("/api/v1/publications").status_code == 200


def test_main_refuses_without_external_config_and_on_wrong_targets(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.delenv(boot.EMAIL_ENV, raising=False)
    monkeypatch.delenv(boot.PASSWORD_ENV, raising=False)
    assert boot.main(["--dry-run", "--expected-database", settings.db_name]) == 2  # no credential config
    monkeypatch.setenv(boot.EMAIL_ENV, EMAIL)
    monkeypatch.setenv(boot.PASSWORD_ENV, PASSWORD)
    monkeypatch.setattr(settings, "db_port", 5432)
    assert boot.main(["--dry-run", "--expected-database", settings.db_name, "--allow-weak-demo-password"]) == 2
    monkeypatch.setattr(settings, "db_port", 55432)
    assert boot.main(["--dry-run", "--expected-database", "wrong_demo_db", "--allow-weak-demo-password"]) == 2
    assert boot.main(["--apply", "--expected-database", settings.db_name]) == 2  # weak password, flag missing


def test_role_option_creates_an_unlinked_read_only_account(db: Session) -> None:
    lecturer = boot.create_admin(db, "viewer@bootstrap.test", "viewer-pass-1", "LECTURER")
    reviewer = boot.create_admin(db, "reviewer@bootstrap.test", "reviewer-pass-1", "REVIEWER")
    assert (lecturer.role, lecturer.lecturer_id) == ("LECTURER", None)
    assert (reviewer.role, reviewer.lecturer_id) == ("REVIEWER", None)
    assert db.scalar(select(func.count()).select_from(Lecturer)) == 0  # no lecturer profile is invented
    actions = db.scalars(select(AuditEvent.after_state["role"].astext).where(AuditEvent.action == "DEMO_ADMIN_BOOTSTRAPPED")).all()
    assert sorted(actions) == ["LECTURER", "REVIEWER"]
    assert boot.plan_for(db, "viewer@bootstrap.test", "viewer-pass-1", "LECTURER").action == "EXISTS_OK"
    # the same account is NOT a usable ADMIN: nothing is ever changed or escalated
    assert boot.plan_for(db, "viewer@bootstrap.test", "viewer-pass-1", "ADMIN").action == "UNSUITABLE"
