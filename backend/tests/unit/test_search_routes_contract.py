"""OpenAPI contract coverage for the Completion-1 A3 global search route."""

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_registers_global_search_path() -> None:
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200, response.text
    paths = response.json()["paths"]
    assert "/api/v1/search" in paths
    assert "get" in paths["/api/v1/search"]