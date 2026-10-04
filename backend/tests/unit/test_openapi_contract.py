"""OpenAPI schema contract coverage."""

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_includes_lecturer_and_author_paths() -> None:
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200, response.text
    paths = response.json()["paths"]
    assert "/api/v1/lecturers/export" in paths
    assert "/api/v1/authors" in paths
    assert "/api/v1/authors/stats" in paths
    assert "/api/v1/authors/{author_id}" in paths
    assert "/api/v1/authors/normalize-import/{import_id}" in paths
