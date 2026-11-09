"""E4 / NFR-15: limit on failed password logins. No database is touched."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_session
from app.core.login_throttle import MAX_FAILURES, WINDOW_SECONDS, LoginThrottle, login_throttle
from app.core.security import password_hasher
from app.main import app
from app.models.governance import User

EMAIL = "giang.vien@example.invalid"
PASSWORD = "Correct-Horse-9"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def throttle(clock: Clock) -> LoginThrottle:
    return LoginThrottle(max_failures=3, window_seconds=60, clock=clock)


def _fail(throttle: LoginThrottle, times: int, email: str = EMAIL) -> None:
    for _ in range(times):
        throttle.record_failure(email)


def test_allowed_until_the_limit_is_reached(throttle: LoginThrottle) -> None:
    _fail(throttle, 2)
    assert throttle.retry_after(EMAIL) == 0
    _fail(throttle, 1)
    assert throttle.retry_after(EMAIL) == 60


def test_block_lifts_when_the_oldest_failure_ages_out(
    throttle: LoginThrottle, clock: Clock
) -> None:
    _fail(throttle, 3)
    clock.now += 59.5
    assert throttle.retry_after(EMAIL) == 1
    clock.now += 0.5
    assert throttle.retry_after(EMAIL) == 0


def test_only_failures_inside_the_window_count(throttle: LoginThrottle, clock: Clock) -> None:
    _fail(throttle, 2)
    clock.now += 61
    _fail(throttle, 1)
    assert throttle.retry_after(EMAIL) == 0


def test_email_is_matched_case_insensitively(throttle: LoginThrottle) -> None:
    _fail(throttle, 3, "  Giang.Vien@Example.INVALID ")
    assert throttle.retry_after(EMAIL) == 60


def test_one_email_does_not_affect_another(throttle: LoginThrottle) -> None:
    _fail(throttle, 3)
    assert throttle.retry_after("khac@example.invalid") == 0


def test_clear_forgets_the_failures(throttle: LoginThrottle) -> None:
    _fail(throttle, 3)
    throttle.clear(EMAIL)
    assert throttle.retry_after(EMAIL) == 0


def test_table_stays_bounded_under_guesses_at_random_emails(clock: Clock) -> None:
    throttle = LoginThrottle(max_failures=3, window_seconds=60, max_tracked=10, clock=clock)
    for number in range(100):
        throttle.record_failure(f"u{number}@example.invalid")
    assert len(throttle._failures) <= 10


# ---------------------------------------------------------------------------
# Through POST /auth/login. No ``with TestClient``: startup work is not needed here.
# ---------------------------------------------------------------------------

def _user() -> User:
    return User(
        id=uuid.uuid4(), email=EMAIL, display_name="Giang Vien", role="LECTURER",
        password_hash=password_hasher.hash(PASSWORD), is_active=True, auth_version=1,
        has_password=True, google_linked=False,
    )


@pytest.fixture
def db() -> MagicMock:
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    return session


@pytest.fixture
def client(db: MagicMock) -> Generator[TestClient, None, None]:
    login_throttle.reset()
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
    login_throttle.reset()


def _login(client: TestClient, password: str, email: str = EMAIL):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_blocked_after_too_many_wrong_passwords_even_with_the_right_one(
    client: TestClient, db: MagicMock
) -> None:
    user = _user()
    db.query.return_value.filter.return_value.first.side_effect = (
        lambda: user if db.query.call_args.args[0] is User else None
    )
    for _ in range(MAX_FAILURES):
        assert _login(client, "sai-mat-khau").json()["code"] == "INVALID_CREDENTIALS"

    blocked = _login(client, PASSWORD)

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "TOO_MANY_LOGIN_ATTEMPTS"
    assert 0 < int(blocked.headers["retry-after"]) <= WINDOW_SECONDS
    assert "5 phút" in blocked.json()["detail"]
    assert "access_token" not in blocked.cookies


def test_unknown_email_is_limited_like_a_known_one(client: TestClient) -> None:
    for _ in range(MAX_FAILURES):
        assert _login(client, "x", "khong.co@example.invalid").status_code == 401
    assert _login(client, "x", "khong.co@example.invalid").status_code == 429


def test_successful_login_clears_earlier_failures(client: TestClient, db: MagicMock) -> None:
    user = _user()
    db.query.return_value.filter.return_value.first.side_effect = (
        lambda: user if db.query.call_args.args[0] is User else None
    )
    for _ in range(MAX_FAILURES - 1):
        _login(client, "sai-mat-khau")
    assert _login(client, PASSWORD).status_code == 200

    assert login_throttle.retry_after(EMAIL) == 0
    for _ in range(MAX_FAILURES - 1):
        assert _login(client, "sai-mat-khau").status_code == 401


def test_blocked_attempt_does_not_touch_the_database(client: TestClient, db: MagicMock) -> None:
    for _ in range(MAX_FAILURES):
        login_throttle.record_failure(EMAIL)
    db.reset_mock()

    assert _login(client, PASSWORD).status_code == 429
    db.query.assert_not_called()
