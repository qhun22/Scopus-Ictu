"""Google Sign-In: who may get in, and how the OAuth state is protected.

Google itself is replaced by ``httpx2.MockTransport``; users and lecturers live in the SQLite
mirror of the schema, so nothing leaves this process.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.api.dependencies import COOKIE_NAME
from app.api.v1.endpoints import auth as auth_module
from app.core.config import settings
from app.core.database import get_session
from app.core.security import password_hasher
from app.main import app
from app.models.governance import AuditEvent, User
from app.models.master_lecturer import Lecturer
from tests.source_staging_fixtures import make_sqlite_engine

ORIGIN = "https://app.example.invalid"
DOMAIN = "ictu.example.invalid"
LOGIN = "/api/v1/auth/google/login"
CALLBACK = "/api/v1/auth/google/callback"


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = make_sqlite_engine()
    with Session(engine, autoflush=False, expire_on_commit=False) as session:
        def assign_ids(flushing: Session, _context, _instances) -> None:
            # PostgreSQL's gen_random_uuid() default does not exist in the SQLite mirror.
            for obj in flushing.new:
                if isinstance(obj, (User, AuditEvent, Lecturer)) and obj.id is None:
                    obj.id = uuid.uuid4()

        event.listen(session, "before_flush", assign_ids)
        yield session


@pytest.fixture
def google_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(settings, "google_oauth_allowed_origins", ORIGIN)
    monkeypatch.setattr(settings, "google_allowed_email_domain", DOMAIN)


@pytest.fixture
def client(db: Session, google_settings: None) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app, base_url="http://testserver", follow_redirects=False)
    app.dependency_overrides.clear()


def _lecturer(db: Session, email: str | None, name: str = "Nguyen Van A") -> Lecturer:
    lecturer = Lecturer(id=uuid.uuid4(), full_name=name, full_name_normalized=name.lower(),
                        email=email)
    db.add(lecturer)
    db.commit()
    return lecturer


def _user(db: Session, email: str, **fields) -> User:
    values = {
        "id": uuid.uuid4(), "email": email, "display_name": "Co San", "role": "ADMIN",
        "password_hash": password_hasher.hash("mat-khau-cu-1"),
    } | fields
    user = User(**values)
    db.add(user)
    db.commit()
    return user


def _google(
    monkeypatch: pytest.MonkeyPatch,
    userinfo: dict,
    *,
    token_status: int = 200,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == auth_module.GOOGLE_TOKEN_URL:
            return httpx2.Response(token_status, json={"access_token": "google-token"})
        assert request.headers["authorization"] == "Bearer google-token"
        return httpx2.Response(200, json=userinfo)

    real_client = httpx2.AsyncClient
    monkeypatch.setattr(
        auth_module.httpx, "AsyncClient",
        lambda **kwargs: real_client(transport=httpx2.MockTransport(handler), **kwargs),
    )


def _start(client: TestClient) -> str:
    """Begin the flow as a browser would; returns the ``state`` Google would echo back."""

    response = client.get(LOGIN, params={"origin": ORIGIN})
    assert response.status_code == 302
    return parse_qs(urlsplit(response.headers["location"]).query)["state"][0]


def _finish(client: TestClient) -> httpx2.Response:
    return client.get(CALLBACK, params={"state": _start(client), "code": "auth-code"})


def _error_of(response: httpx2.Response) -> str | None:
    query = parse_qs(urlsplit(response.headers["location"]).query)
    return query.get("google_error", [None])[0]


def _userinfo(email: str, **extra) -> dict:
    return {"email": email, "email_verified": True, **extra}


# --- starting the flow -----------------------------------------------------------------------

def test_login_refuses_when_google_is_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "google_client_id", None)

    response = client.get(LOGIN, params={"origin": ORIGIN})

    assert response.status_code == 503
    assert response.json()["code"] == "GOOGLE_OAUTH_NOT_CONFIGURED"


def test_login_redirects_to_google_with_the_callback_on_the_callers_origin(
    client: TestClient,
) -> None:
    response = client.get(LOGIN, params={"origin": ORIGIN})

    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert response.headers["location"].startswith(auth_module.GOOGLE_AUTHORIZE_URL)
    assert query["redirect_uri"] == [f"{ORIGIN}{CALLBACK}"]
    assert query["state"][0]
    assert auth_module.GOOGLE_STATE_COOKIE in response.cookies


@pytest.mark.parametrize("origin", ["https://evil.example.invalid", f"{ORIGIN}.evil.invalid"])
def test_login_refuses_an_origin_outside_the_allow_list(client: TestClient, origin: str) -> None:
    response = client.get(LOGIN, params={"origin": origin})

    assert response.status_code == 400
    assert response.json()["code"] == "GOOGLE_OAUTH_ORIGIN_NOT_ALLOWED"


# --- the OAuth state -------------------------------------------------------------------------

def test_callback_without_the_state_cookie_is_refused(client: TestClient) -> None:
    response = client.get(CALLBACK, params={"state": "x", "code": "c"})

    assert _error_of(response) == "state"
    assert COOKIE_NAME not in response.cookies


def test_callback_with_a_state_that_does_not_match_is_refused(client: TestClient) -> None:
    _start(client)

    response = client.get(CALLBACK, params={"state": "gia-mao", "code": "c"})

    assert _error_of(response) == "state"
    assert COOKIE_NAME not in response.cookies


def test_user_cancelling_at_google_is_reported(client: TestClient) -> None:
    response = client.get(CALLBACK, params={"state": _start(client), "error": "access_denied"})

    assert _error_of(response) == "denied"


# --- what Google says about the person -------------------------------------------------------

def test_token_exchange_failure_is_reported(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _google(monkeypatch, {}, token_status=400)

    assert _error_of(_finish(client)) == "token_exchange"


def test_unverified_email_is_refused(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _user(db, f"a@{DOMAIN}")
    _google(monkeypatch, {"email": f"a@{DOMAIN}", "email_verified": False})

    response = _finish(client)

    assert _error_of(response) == "email_unverified"
    assert COOKIE_NAME not in response.cookies


def test_email_outside_the_domain_is_refused(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _user(db, "a@gmail.example.invalid")
    _google(monkeypatch, _userinfo("a@gmail.example.invalid"))

    assert _error_of(_finish(client)) == "domain"


# --- who is allowed in -----------------------------------------------------------------------

def test_existing_user_logs_in_and_is_marked_google_linked(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user(db, f"Admin@{DOMAIN}")
    _google(monkeypatch, _userinfo(f"admin@{DOMAIN}", picture="https://x.invalid/a.png"))

    response = _finish(client)

    assert response.status_code == 302 and response.headers["location"] == "/"
    assert COOKIE_NAME in response.cookies
    db.refresh(user)
    assert user.google_linked is True
    assert user.has_password is True  # An existing password keeps working.
    assert user.avatar_url == "https://x.invalid/a.png"
    assert user.role == "ADMIN"  # Never downgraded or changed by Google login.


def test_lecturer_in_the_dataset_gets_a_lecturer_account_without_a_password(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturer = _lecturer(db, f"gv@{DOMAIN}", "Tran Thi B")
    _google(monkeypatch, _userinfo(f"GV@{DOMAIN}"))

    response = _finish(client)

    assert COOKIE_NAME in response.cookies
    user = db.scalars(select(User)).one()
    assert (user.role, user.lecturer_id) == ("LECTURER", lecturer.id)
    assert (user.has_password, user.google_linked) == (False, True)
    audit = db.scalars(select(AuditEvent)).one()
    assert audit.action == "USER_PROVISIONED_GOOGLE"
    assert audit.entity_id == user.id


@pytest.mark.parametrize(
    "arrange",
    [
        pytest.param(lambda db: None, id="student-not-in-the-dataset"),
        pytest.param(
            lambda db: (_lecturer(db, f"x@{DOMAIN}", "A"), _lecturer(db, f"x@{DOMAIN}", "B")),
            id="two-lecturers-share-the-email",
        ),
        pytest.param(
            lambda db: _user(db, f"khac@{DOMAIN}", role="LECTURER",
                             lecturer_id=_lecturer(db, f"x@{DOMAIN}").id),
            id="lecturer-already-linked-to-another-account",
        ),
    ],
)
def test_nobody_else_gets_an_account(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    arrange: Callable[[Session], object],
) -> None:
    arrange(db)
    before = len(db.scalars(select(User)).all())
    _google(monkeypatch, _userinfo(f"x@{DOMAIN}"))

    response = _finish(client)

    assert _error_of(response) == "not_lecturer"
    assert COOKIE_NAME not in response.cookies
    assert len(db.scalars(select(User)).all()) == before


def test_locked_account_cannot_log_in_through_google(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _user(db, f"khoa@{DOMAIN}", is_active=False)
    _google(monkeypatch, _userinfo(f"khoa@{DOMAIN}"))

    response = _finish(client)

    assert _error_of(response) == "locked"
    assert COOKIE_NAME not in response.cookies
