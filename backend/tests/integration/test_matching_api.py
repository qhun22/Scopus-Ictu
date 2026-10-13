"""ADMIN candidate generation + Craw ingestion endpoints under /matching.

Runs only against the isolated PostgreSQL test database (TEST_DATABASE_URL),
same convention as test_generate_matching_candidates_cli.py and
test_ingest_craw_known_publications_cli.py. These tests exercise the
end-to-end web path (RBAC -> workflow service -> real persistence), not
just the pure in-memory discovery logic already covered by
test_craw_assisted_discovery.py.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor

NOW = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
BASE = "https://repository.ictu.edu.vn"

_TABLES_TO_TRUNCATE = (
    "lecturer_scopus_candidate_reviews",
    "identity_evidence",
    "lecturer_scopus_identities",
    "lecturer_scopus_candidate_evidence",
    "lecturer_scopus_candidate_observations",
    "lecturer_scopus_candidates",
    "candidate_generation_runs",
    "lecturer_known_publications",
    "lecturer_source_snapshots",
    "publication_authors",
    "scopus_author_name_variants",
    "scopus_authors",
    "publications",
    "lecturers",
)


@pytest.fixture
def db_session(isolated_db_engine: Engine | None) -> Generator[Session, None, None]:
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL database available.")
    Base.metadata.create_all(bind=isolated_db_engine)
    with Session(isolated_db_engine) as cleanup:
        for table in _TABLES_TO_TRUNCATE:
            cleanup.execute(text(f'TRUNCATE "{table}" CASCADE'))
        cleanup.commit()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=isolated_db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(role: str) -> User:
    return User(
        id=uuid.uuid4(), email=f"{role.lower()}-{uuid.uuid4().hex[:6]}@match.test", password_hash="x",
        display_name=role, role=role, lecturer_id=None, is_active=True, version=1, auth_version=1,
        created_at=NOW, updated_at=NOW,
    )


@pytest.fixture
def as_role(db_session: Session):
    def _as(role: str) -> User:
        user = _user(role)
        db_session.add(user)
        db_session.commit()
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _as


# --------------------------------------------------------------------------- RBAC
@pytest.mark.parametrize("role", ["LECTURER", "REVIEWER"])
def test_only_admin_can_generate_candidates(client, as_role, role) -> None:
    as_role(role)
    assert client.post("/api/v1/matching/candidates/generate").status_code == 403


@pytest.mark.parametrize("role", ["LECTURER", "REVIEWER"])
def test_only_admin_can_use_craw_ingestion(client, as_role, role) -> None:
    as_role(role)
    assert client.post("/api/v1/matching/craw/preview").status_code == 403
    assert client.post(
        "/api/v1/matching/craw/apply", json={"fingerprint": "x", "confirm": True}
    ).status_code == 403


def test_anonymous_is_unauthenticated(client) -> None:
    assert client.post("/api/v1/matching/candidates/generate").status_code == 401


# --------------------------------------------------------------------------- candidate generation
def test_name_match_generates_exactly_one_candidate_no_craw_data(client, as_role, db_session) -> None:
    db_session.add_all(
        [
            Lecturer(full_name="Nguyen Van A", full_name_normalized="nguyen van a"),
            ScopusAuthor(scopus_id="11111111111", preferred_name="Nguyen Van A"),
        ]
    )
    db_session.commit()
    as_role("ADMIN")

    response = client.post("/api/v1/matching/candidates/generate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["candidate_roots"] == 1
    assert body["name_candidates"] == 1
    assert body["craw_assisted_candidates"] == 0
    assert body["craw_unattributed"] == 0
    assert body["idempotent_replay"] is False


def test_rerunning_generation_is_idempotent_and_never_duplicates(client, as_role, db_session) -> None:
    db_session.add_all(
        [
            Lecturer(full_name="Nguyen Van A", full_name_normalized="nguyen van a"),
            ScopusAuthor(scopus_id="11111111111", preferred_name="Nguyen Van A"),
        ]
    )
    db_session.commit()
    as_role("ADMIN")

    first_response = client.post("/api/v1/matching/candidates/generate")
    second_response = client.post("/api/v1/matching/candidates/generate")
    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    first, second = first_response.json(), second_response.json()
    # Each click mints its own run_id (never request-supplied), so these are
    # two distinct COMPLETED runs over the same unchanged source data —
    # the invariant under test is the candidate ROOT COUNT never duplicates.
    assert first["run_id"] != second["run_id"]
    assert second["candidate_roots"] == 1


def test_five_author_publication_with_one_ictu_match_does_not_mass_generate(
    client, as_role, db_session, monkeypatch, tmp_path
) -> None:
    """End-to-end version of the core negative case: a Craw-known
    publication reconciling to a 5-author Scopus paper must produce exactly
    ONE new Craw-assisted candidate (the name-anchored author), not five."""
    lecturer = Lecturer(
        full_name="Tran Thi Mai",
        full_name_normalized="tran thi mai",
        repository_profile_url=f"{BASE}/giang-vien/mai/",
    )
    publication = Publication(
        eid="2-s2.0-five-authors",
        doi="10.1/five-authors",
        title="Five Author Paper",
        title_normalized="five author paper",
    )
    # "Mai T.T." shares the "mai" token with the lecturer's full name (so the
    # weak Craw-discovery overlap check anchors it) but matches NONE of the 4
    # strict name_generator rules (no reordering/abbreviation handling there)
    # — this is exactly the gap Craw-assisted discovery exists to close.
    matching_author = ScopusAuthor(scopus_id="90000000001", preferred_name="Mai T.T.")
    unrelated_authors = [
        ScopusAuthor(scopus_id=f"9000000000{i}", preferred_name=name)
        for i, name in enumerate(["John Smith", "Maria Garcia", "Wei Zhang", "Alex Johnson"], start=2)
    ]
    db_session.add_all([lecturer, publication, matching_author, *unrelated_authors])
    db_session.commit()

    db_session.add_all(
        [
            PublicationAuthor(
                publication_id=publication.id, scopus_author_id=matching_author.id, author_order=1
            ),
            *[
                PublicationAuthor(
                    publication_id=publication.id, scopus_author_id=author.id, author_order=order
                )
                for order, author in enumerate(unrelated_authors, start=2)
            ],
        ]
    )
    db_session.commit()

    craw_dir = tmp_path / "craw"
    craw_dir.mkdir(parents=True, exist_ok=True)
    (craw_dir / "lecturers.json").write_text(
        json.dumps(
            [
                {
                    "source_id": f"{BASE}/giang-vien/mai/",
                    "full_name": "Tran Thi Mai",
                    "profile_url": f"{BASE}/giang-vien/mai/",
                }
            ]
        ),
        encoding="utf-8",
    )
    (craw_dir / "publications.json").write_text(
        json.dumps(
            [
                {
                    "source_id": f"{BASE}/bai-bao/five-authors/",
                    "title": "Five Author Paper",
                    "doi": "10.1/five-authors",
                    "year": "2020",
                }
            ]
        ),
        encoding="utf-8",
    )
    (craw_dir / "lecturer_publication_links.json").write_text(
        json.dumps(
            [
                {
                    "lecturer_source_id": f"{BASE}/giang-vien/mai/",
                    "target_source_id": f"{BASE}/bai-bao/five-authors/",
                    "relationship_source": "ictu_lecturer_profile",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "craw_source_dir", str(craw_dir), raising=False)
    as_role("ADMIN")

    preview = client.post("/api/v1/matching/craw/preview").json()
    assert preview["can_apply"] is True, preview
    apply_response = client.post(
        "/api/v1/matching/craw/apply",
        json={"fingerprint": preview["fingerprint"], "confirm": True},
    )
    assert apply_response.status_code == 200, apply_response.text

    generation = client.post("/api/v1/matching/candidates/generate").json()
    # Name step finds nothing (no lecturer name matches any of the 5
    # authors via the 4 strict rules); Craw-assisted discovery must
    # anchor exactly the one name-overlapping author position.
    assert generation["name_candidates"] == 0
    assert generation["craw_assisted_candidates"] == 1
    assert generation["craw_unattributed"] == 4
    assert generation["candidate_roots"] == 1


# --------------------------------------------------------------------------- Craw ingestion
def test_craw_source_not_configured_is_reported(client, as_role, monkeypatch) -> None:
    monkeypatch.setattr(settings, "craw_source_dir", None, raising=False)
    as_role("ADMIN")
    preview = client.post("/api/v1/matching/craw/preview").json()
    assert preview["can_apply"] is False
    assert preview["blocked_reason"] == "CRAW_SOURCE_NOT_CONFIGURED"


def test_apply_without_confirm_is_rejected(client, as_role) -> None:
    as_role("ADMIN")
    response = client.post("/api/v1/matching/craw/apply", json={"fingerprint": "x", "confirm": False})
    assert response.status_code == 422


def _write_craw_fixture(craw_dir: Path) -> None:
    craw_dir.mkdir(parents=True, exist_ok=True)
    (craw_dir / "lecturers.json").write_text(
        json.dumps(
            [
                {
                    "source_id": f"{BASE}/giang-vien/a/",
                    "full_name": "Nguyen Van A",
                    "profile_url": f"{BASE}/giang-vien/a/",
                }
            ]
        ),
        encoding="utf-8",
    )
    (craw_dir / "publications.json").write_text(
        json.dumps(
            [
                {
                    "source_id": f"{BASE}/bai-bao/p1/",
                    "title": "Paper one",
                    "doi": "10.1/one",
                    "year": "2020",
                }
            ]
        ),
        encoding="utf-8",
    )
    (craw_dir / "lecturer_publication_links.json").write_text(
        json.dumps(
            [
                {
                    "lecturer_source_id": f"{BASE}/giang-vien/a/",
                    "target_source_id": f"{BASE}/bai-bao/p1/",
                    "relationship_source": "ictu_lecturer_profile",
                }
            ]
        ),
        encoding="utf-8",
    )


def test_craw_preview_then_apply_writes_snapshot_and_known_publication(
    client, as_role, db_session, monkeypatch, tmp_path
) -> None:
    db_session.add(
        Lecturer(
            full_name="Nguyen Van A",
            full_name_normalized="nguyen van a",
            repository_profile_url=f"{BASE}/giang-vien/a/",
        )
    )
    db_session.commit()
    craw_dir = tmp_path / "craw"
    _write_craw_fixture(craw_dir)
    monkeypatch.setattr(settings, "craw_source_dir", str(craw_dir), raising=False)
    as_role("ADMIN")

    preview = client.post("/api/v1/matching/craw/preview").json()
    assert preview["can_apply"] is True, preview
    assert preview["preview"]["mapped_lecturer_count"] == 1
    assert preview["preview"]["known_publications_to_create"] == 1

    apply_response = client.post(
        "/api/v1/matching/craw/apply",
        json={"fingerprint": preview["fingerprint"], "confirm": True},
    )
    assert apply_response.status_code == 200, apply_response.text
    body = apply_response.json()
    assert body["result"]["snapshots_created"] == 1
    assert body["result"]["known_publications_created"] == 1


def test_craw_apply_with_stale_fingerprint_is_rejected(
    client, as_role, db_session, monkeypatch, tmp_path
) -> None:
    db_session.add(
        Lecturer(
            full_name="Nguyen Van A",
            full_name_normalized="nguyen van a",
            repository_profile_url=f"{BASE}/giang-vien/a/",
        )
    )
    db_session.commit()
    craw_dir = tmp_path / "craw"
    _write_craw_fixture(craw_dir)
    monkeypatch.setattr(settings, "craw_source_dir", str(craw_dir), raising=False)
    as_role("ADMIN")

    response = client.post(
        "/api/v1/matching/craw/apply", json={"fingerprint": "not-the-real-fingerprint", "confirm": True}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "PREVIEW_STALE"


def test_craw_apply_is_idempotent_on_rerun(
    client, as_role, db_session, monkeypatch, tmp_path
) -> None:
    db_session.add(
        Lecturer(
            full_name="Nguyen Van A",
            full_name_normalized="nguyen van a",
            repository_profile_url=f"{BASE}/giang-vien/a/",
        )
    )
    db_session.commit()
    craw_dir = tmp_path / "craw"
    _write_craw_fixture(craw_dir)
    monkeypatch.setattr(settings, "craw_source_dir", str(craw_dir), raising=False)
    as_role("ADMIN")

    first_preview = client.post("/api/v1/matching/craw/preview").json()
    client.post(
        "/api/v1/matching/craw/apply",
        json={"fingerprint": first_preview["fingerprint"], "confirm": True},
    )

    second_preview = client.post("/api/v1/matching/craw/preview").json()
    second_apply = client.post(
        "/api/v1/matching/craw/apply",
        json={"fingerprint": second_preview["fingerprint"], "confirm": True},
    )
    assert second_apply.status_code == 200, second_apply.text
    result = second_apply.json()["result"]
    assert result["snapshots_created"] == 0
    assert result["snapshots_reused"] == 1
    assert result["known_publications_created"] == 0
    assert result["known_publications_reused"] == 1
