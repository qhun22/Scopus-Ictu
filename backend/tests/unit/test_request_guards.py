"""A NUL character in the URL is answered with 422 instead of reaching PostgreSQL."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.request_guards import INVALID_CHARACTER_CODE, reject_nul_in_url
from app.schemas.auth import LoginRequest


def make_client() -> TestClient:
    app = FastAPI()
    app.middleware("http")(reject_nul_in_url)

    @app.get("/items")
    def items(q: str = "") -> dict[str, str]:
        return {"q": q}

    @app.get("/items/{key}")
    def item(key: str) -> dict[str, str]:
        return {"key": key}

    return TestClient(app)


@pytest.mark.parametrize("url", ["/items?q=%00", "/items?q=a%00b", "/items?q=%00&x=1"])
def test_nul_in_query_is_rejected_with_422(url: str) -> None:
    response = make_client().get(url)
    assert response.status_code == 422
    assert response.json()["code"] == INVALID_CHARACTER_CODE
    assert "detail" in response.json()


def test_nul_in_path_is_rejected_with_422() -> None:
    response = make_client().get("/items/%00")
    assert response.status_code == 422
    assert response.json()["code"] == INVALID_CHARACTER_CODE


def test_normal_and_double_encoded_values_pass() -> None:
    client = make_client()
    assert client.get("/items?q=hello").json() == {"q": "hello"}
    assert client.get("/items/abc").json() == {"key": "abc"}
    # %2500 decodes to the four characters "%00", not to a NUL character.
    assert client.get("/items?q=%2500").json() == {"q": "%00"}
    assert client.get("/items?q=Nguy%E1%BB%85n").json() == {"q": "Nguyễn"}


@pytest.mark.parametrize("field", ["email", "password"])
def test_login_payload_rejects_nul(field: str) -> None:
    payload = {"email": "a@example.invalid", "password": "x"}
    payload[field] = "ab\x00cd"
    with pytest.raises(ValidationError):
        LoginRequest(**payload)


def test_login_payload_accepts_normal_values() -> None:
    assert LoginRequest(email="a@example.invalid", password="x").email == "a@example.invalid"
