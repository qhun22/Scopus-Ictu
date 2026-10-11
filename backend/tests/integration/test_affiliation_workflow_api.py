"""ADMIN affiliation workflow (overview -> preview -> apply), isolated schema per test.

Synthetic data only.  The workflow must work with 0 lecturers, rebuild author
slots from stored raw CSV rows, never read a path from a request, and never
trust more than the source bundle supports.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.models.governance import AuditEvent, User
from app.models.publication import Publication, PublicationAuthor, PublicationRawSource, ScopusAuthor
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services import affiliation_workflow as workflow

NOW = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)
ORCID = "0000-0001-0000-0042"
RETRIEVED = "2026-10-09T01:00:00+00:00"
H = "a" * 64


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("never target an acceptance database")
    schema = f"test_aff_wf_{uuid.uuid4().hex}"
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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(role: str) -> User:
    return User(
        id=uuid.uuid4(), email=f"{role.lower()}-{uuid.uuid4().hex[:6]}@aff.test", password_hash="x",
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


def _openalex(doi: str, names: list[tuple[str, str | None]]) -> dict:
    return {
        "retrieved_at": RETRIEVED, "source": "openalex", "query_doi": doi,
        "work": {
            "id": "https://openalex.org/W1", "doi": f"https://doi.org/{doi}",
            "authorships": [
                {
                    "author": {"display_name": n, "orcid": f"https://orcid.org/{o}" if o else None},
                    "raw_affiliation_strings": [f"Dept of {n}, Univ X"],
                    "affiliations": [{"raw_affiliation_string": f"Dept of {n}, Univ X", "institution_ids": ["I1"]}],
                    "institutions": [{"id": "I1", "display_name": "Univ X", "ror": None, "country_code": "VN"}],
                }
                for n, o in names
            ],
        },
    }


def _bundle(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "openalex_works.jsonl").write_text(
        json.dumps(_openalex("10.1/one", [("Ann A.", ORCID), ("Bob Beta", None)])) + "\n", encoding="utf-8"
    )
    (directory / "crossref_works.jsonl").write_text(
        json.dumps({"retrieved_at": RETRIEVED, "source": "crossref", "query_doi": "10.1/one", "http": 404}) + "\n",
        encoding="utf-8",
    )
    (directory / "orcid_external_ids.json").write_text(
        json.dumps({ORCID: {"retrieved_at": RETRIEVED, "http": 200, "external_identifiers": [
            {"type": "Scopus Author ID", "value": "111111", "url": None, "source": "Scopus - Elsevier"}]}}),
        encoding="utf-8",
    )
    return directory


def _paper(db: Session, imp: ScopusImport, row_number: int, eid: str, doi: str | None, ids: str, names: str) -> None:
    pub = Publication(
        id=uuid.uuid4(), eid=eid, doi=doi, title=f"Title {eid}", title_normalized=f"title {eid}".casefold(),
        source_title="Journal", year=2024, volume=None, issue=None, art_no=None, page_start=None, page_end=None,
        cited_by_count=0, document_type="Article", publication_stage="Final", open_access_status=None,
        version=1, created_at=NOW, updated_at=NOW,
    )
    payload = {"EID": eid, "DOI": doi or "", "Author(s) ID": ids, "Author full names": names}
    raw = RawScopusRecord(
        id=uuid.uuid4(), import_id=imp.id, row_number=row_number, row_hash=f"{row_number:064d}",
        eid_raw=eid, doi_raw=doi, raw_payload=payload, validation_status="VALID", created_at=NOW,
    )
    db.add_all([pub, raw])
    db.flush()
    db.add(PublicationRawSource(publication_id=pub.id, raw_record_id=raw.id))
    for order, sid in enumerate([x.strip() for x in ids.split(";") if x.strip()], start=1):
        author = db.query(ScopusAuthor).filter_by(scopus_id=sid).one_or_none() or ScopusAuthor(
            scopus_id=sid, preferred_name=f"Author {sid}")
        db.add(author)
        db.flush()
        db.add(PublicationAuthor(publication_id=pub.id, scopus_author_id=author.id, author_order=order))


@pytest.fixture
def world(db_session: Session) -> None:
    """Zero lecturers.  E1 is covered by the bundle, E2 (a "new CSV" paper) is not."""

    imp = ScopusImport(
        id=uuid.uuid4(), file_name="new.csv", file_sha256="b" * 64, total_records=2, valid_records=2,
        invalid_records=0, status="APPLIED", version=1, created_at=NOW, updated_at=NOW,
    )
    db_session.add(imp)
    db_session.flush()
    _paper(db_session, imp, 2, "E1", "10.1/one", "111111; 222222", "Alpha, Ann (111111); Beta, Bob (222222)")
    _paper(db_session, imp, 3, "E2", "10.9/not-in-the-bundle", "333333", "Gamma, Gus (333333)")
    db_session.commit()


@pytest.fixture
def bundle_dir(tmp_path, monkeypatch) -> Path:
    directory = _bundle(tmp_path / "bundle")
    monkeypatch.setattr(settings, "affiliation_source_dir", str(directory), raising=False)
    return directory


def _preview(client: TestClient) -> dict:
    response = client.post("/api/v1/affiliations/preview")
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- RBAC
@pytest.mark.parametrize("role", ["LECTURER", "REVIEWER"])
def test_only_admin_can_use_the_workflow(client, as_role, role, world, bundle_dir) -> None:
    as_role(role)
    assert client.get("/api/v1/affiliations/overview").status_code == 403
    assert client.post("/api/v1/affiliations/preview").status_code == 403
    assert client.post("/api/v1/affiliations/apply", json={"fingerprint": H, "confirm": True}).status_code == 403


def test_anonymous_is_unauthenticated(client) -> None:
    assert client.get("/api/v1/affiliations/overview").status_code == 401


# --------------------------------------------------------------------------- bundle availability
def test_unconfigured_source_is_reported_and_blocks_apply(client, as_role, world, monkeypatch) -> None:
    monkeypatch.setattr(settings, "affiliation_source_dir", None, raising=False)
    as_role("ADMIN")
    overview = client.get("/api/v1/affiliations/overview").json()
    assert overview["source"]["configured"] is False and overview["source"]["ready"] is False
    assert "SOURCE_DIR_NOT_CONFIGURED" in overview["source"]["problems"]
    body = _preview(client)
    assert body["can_apply"] is False and body["blocked_reason"] == "SOURCE_DIR_NOT_CONFIGURED"
    response = client.post("/api/v1/affiliations/apply", json={"fingerprint": H, "confirm": True})
    assert response.status_code == 409


def test_incomplete_bundle_is_not_ready(client, as_role, world, bundle_dir) -> None:
    (bundle_dir / "orcid_external_ids.json").unlink()
    as_role("ADMIN")
    source = client.get("/api/v1/affiliations/overview").json()["source"]
    assert source["ready"] is False and "MISSING_orcid_external_ids.json" in source["problems"]


def test_overview_never_exposes_the_server_path(client, as_role, world, bundle_dir) -> None:
    as_role("ADMIN")
    text_body = client.get("/api/v1/affiliations/overview").text
    assert str(bundle_dir) not in text_body and bundle_dir.name in text_body


# --------------------------------------------------------------------------- preview / apply
def test_full_flow_without_any_lecturer(client, as_role, db_session, world, bundle_dir) -> None:
    admin = as_role("ADMIN")
    assert db_session.execute(text("select count(*) from lecturers")).scalar() == 0
    preview = _preview(client)
    assert preview["can_apply"] is True and preview["publications"] == 2
    assert preview["input"]["papers_with_any_work"] == 1 and preview["input"]["papers_without_any_work"] == 1
    assert preview["input"]["cross_check_against_survey_jsonl"] is False  # JSONL is optional
    assert preview["resolutions_to_insert"] == 2 * 2 + 1 * 2  # (2 authors + 1 author) x 2 sources
    # preview is read-only
    assert db_session.execute(text("select count(*) from publication_author_affiliation_resolutions")).scalar() == 0

    missing_confirm = client.post("/api/v1/affiliations/apply", json={"fingerprint": preview["fingerprint"], "confirm": False})
    assert missing_confirm.status_code == 422 and missing_confirm.json()["code"] == "CONFIRMATION_REQUIRED"
    wrong = client.post("/api/v1/affiliations/apply", json={"fingerprint": "0" * 64, "confirm": True})
    assert wrong.status_code == 409 and wrong.json()["code"] == "PREVIEW_STALE"

    ok = client.post("/api/v1/affiliations/apply", json={"fingerprint": preview["fingerprint"], "confirm": True})
    assert ok.status_code == 200, ok.text
    assert ok.json()["result"]["resolutions_to_insert"] == preview["resolutions_to_insert"]
    assert db_session.execute(text("select count(*) from publication_author_affiliation_resolutions")).scalar() == 6
    audit = db_session.query(AuditEvent).filter_by(action=workflow.APPLIED_ACTION).one()
    assert audit.actor_user_id == admin.id and audit.event_metadata["fingerprint"] == preview["fingerprint"]
    assert db_session.execute(text("select count(*) from lecturers")).scalar() == 0

    # Publication detail: verified author keeps the unit, cross-checked author is NOT verified,
    # the paper absent from the bundle stays UNRESOLVED with no invented unit.
    e1 = client.get("/api/v1/publications/E1").json()
    first, second = e1["authors"]
    assert first["affiliation_status"] == "VERIFIED" and first["affiliations"]
    assert second["affiliation_status"] == "CORROBORATED" and second["affiliation_status"] != "VERIFIED"
    e2 = client.get("/api/v1/publications/E2").json()
    assert e2["authors"][0]["affiliation_status"] == "UNRESOLVED" and e2["authors"][0]["affiliations"] == []
    assert {r["unresolved_reason"] for r in e2["authors"][0]["affiliation_resolutions"]} == {"NO_EXTERNAL_WORK"}

    # Applying again is a no-op: refused, nothing duplicated.
    again = _preview(client)
    assert again["can_apply"] is False and again["blocked_reason"] == "NOTHING_TO_APPLY"
    assert client.post("/api/v1/affiliations/apply", json={"fingerprint": again["fingerprint"], "confirm": True}).status_code == 409
    assert db_session.execute(text("select count(*) from publication_author_affiliation_resolutions")).scalar() == 6
    overview = client.get("/api/v1/affiliations/overview").json()
    assert overview["database"]["last_run"]["action"] == workflow.APPLIED_ACTION


def test_request_cannot_choose_a_path(client, as_role, world, bundle_dir) -> None:
    as_role("ADMIN")
    fingerprint = _preview(client)["fingerprint"]
    response = client.post(
        "/api/v1/affiliations/apply",
        json={"fingerprint": fingerprint, "confirm": True, "survey_dir": "C:/Windows", "source_dir": "/etc"},
    )
    assert response.status_code == 422


def test_apply_is_refused_when_data_changed_after_preview(client, as_role, db_session, world, bundle_dir) -> None:
    as_role("ADMIN")
    fingerprint = _preview(client)["fingerprint"]
    imp = db_session.query(ScopusImport).one()
    _paper(db_session, imp, 4, "E3", "10.1/one", "444444", "Delta, Dan (444444)")  # changes the input set (and makes DOI ambiguous)
    db_session.commit()
    response = client.post("/api/v1/affiliations/apply", json={"fingerprint": fingerprint, "confirm": True})
    assert response.status_code == 409 and response.json()["code"] == "PREVIEW_STALE"
    assert db_session.execute(text("select count(*) from publication_author_affiliation_resolutions")).scalar() == 0


def test_concurrent_apply_is_refused(client, as_role, world, bundle_dir, db_session) -> None:
    as_role("ADMIN")
    fingerprint = _preview(client)["fingerprint"]
    url = os.environ["TEST_DATABASE_URL"]
    other = create_engine(url, future=True).connect()
    try:
        other.execute(text("select pg_advisory_lock(:k)"), {"k": workflow._LOCK_KEY})
        response = client.post("/api/v1/affiliations/apply", json={"fingerprint": fingerprint, "confirm": True})
        assert response.status_code == 409 and response.json()["code"] == "AFFILIATION_APPLY_IN_PROGRESS"
    finally:
        other.execute(text("select pg_advisory_unlock(:k)"), {"k": workflow._LOCK_KEY})
        other.close()
    assert db_session.execute(text("select count(*) from publication_author_affiliation_resolutions")).scalar() == 0


def test_tampered_survey_jsonl_blocks_apply(client, as_role, world, bundle_dir, db_session) -> None:
    rows = [
        {"eid": "E1", "doi": "10.1/one", "scopus_author_id": "222222", "author_order": 2, "source": "openalex",
         "link_status": "VERIFIED", "unresolved_reason": None, "evidence": None, "external_position": 2},
    ]
    (bundle_dir / "author_affiliation_links.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    as_role("ADMIN")
    body = _preview(client)
    assert body["source_mismatches"] > 0 and body["can_apply"] is False and body["blocked_reason"] == "SOURCE_MISMATCH"
    response = client.post("/api/v1/affiliations/apply", json={"fingerprint": body["fingerprint"], "confirm": True})
    assert response.status_code == 409
    assert db_session.execute(text("select count(*) from publication_author_affiliation_resolutions")).scalar() == 0


def test_survey_jsonl_for_other_papers_does_not_block_an_unrelated_csv(client, as_role, world, bundle_dir, db_session) -> None:
    """A bundle prepared for a bigger/different CSV: rows of other papers are ignored, covered papers are still checked."""

    from app.services.author_affiliation import (
        align_paper, parse_openalex_authorships, parse_orcid_scopus_ids, parse_scopus_author_slots, unresolved_no_work,
    )

    bridge = {ORCID: parse_orcid_scopus_ids([{"type": "Scopus Author ID", "value": "111111"}])}
    work = _openalex("10.1/one", [("Ann A.", ORCID), ("Bob Beta", None)])["work"]
    slots = parse_scopus_author_slots("111111; 222222", "Alpha, Ann (111111); Beta, Bob (222222)")
    rows = []
    for source in ("openalex", "crossref"):
        links = (align_paper(slots, parse_openalex_authorships(work), bridge, source=source)
                 if source == "openalex" else unresolved_no_work(slots, source=source))
        for link in links:
            rows.append({"eid": "E1", "doi": "10.1/one", "scopus_author_id": link.scopus_id, "author_order": link.author_order,
                         "source": source, "link_status": link.status, "unresolved_reason": link.reason,
                         "evidence": link.evidence, "external_position": link.external_position})
    # a row of a paper that is NOT in this database must be ignored, not reported as a mismatch
    rows.append({"eid": "E-OTHER-CSV", "scopus_author_id": "9", "source": "openalex", "author_order": 1, "link_status": "VERIFIED",
                 "unresolved_reason": None, "evidence": None, "external_position": 1})
    (bundle_dir / "author_affiliation_links.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    as_role("ADMIN")
    body = _preview(client)
    assert body["source_mismatches"] == 0 and body["can_apply"] is True
    stats = body["input"]
    assert stats["cross_check_against_survey_jsonl"] is True
    assert stats["cross_check_links_matched"] == 4          # E1: 2 authors x 2 sources agree with the JSONL
    assert stats["cross_check_links_not_covered"] == 2      # E2's single author x 2 sources are not in the JSONL
    assert client.post("/api/v1/affiliations/apply", json={"fingerprint": body["fingerprint"], "confirm": True}).status_code == 200
